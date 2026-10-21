"""Build and evaluate past-only expected league-bonus projections."""
import json
from pathlib import Path

import numpy as np
import polars as pl
import yaml
from scipy.stats import spearmanr

from ffm.backtest import coverage, pinball_crps
from ffm.distributions import POSITIONS, QuantileModel
from ffm.expected_bonus import walk_forward_bonus
from ffm.ids import normalize_team
from ffm.pbp_bonus import BONUS_COLUMNS, aggregate_bonus_stats

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"
TEST_SEASONS = (2023, 2024, 2025, 2026)
PROJECTION_COLUMNS = (
    "pass_yd", "rush_yd", "rec_yd", "pass_td", "rush_td", "rec_td",
)
ACTUAL_COLUMNS = (
    "passing_yards", "rushing_yards", "receiving_yards",
    "passing_tds", "rushing_tds", "receiving_tds",
)


def projection_stats() -> pl.DataFrame:
    frames = []
    for path in sorted(CACHE.glob("sleeper_projections_*_w*.parquet")):
        schema = pl.read_parquet_schema(path)
        columns = ["player_id", "season", "week", *[c for c in PROJECTION_COLUMNS if c in schema]]
        frame = pl.read_parquet(path, columns=columns)
        for column in PROJECTION_COLUMNS:
            if column not in frame.columns:
                frame = frame.with_columns(pl.lit(0.0).alias(column))
        frames.append(frame.select("player_id", "season", "week", *PROJECTION_COLUMNS))
    return (
        pl.concat(frames, how="diagonal_relaxed")
        .unique(["player_id", "season", "week"], keep="last")
        .rename({"player_id": "sleeper_id", **{c: f"proj_{c}" for c in PROJECTION_COLUMNS}})
    )


def actual_stats() -> pl.DataFrame:
    frame = pl.read_parquet(CACHE / "nflverse_player_stats.parquet")
    return (
        frame.filter(pl.col("season_type") == "REG")
        .select("player_id", "season", "week", *ACTUAL_COLUMNS)
        .unique(["player_id", "season", "week"], keep="last")
        .rename({
            "player_id": "gsis_id",
            "passing_yards": "actual_pass_yd", "rushing_yards": "actual_rush_yd",
            "receiving_yards": "actual_rec_yd", "passing_tds": "actual_pass_td",
            "rushing_tds": "actual_rush_td", "receiving_tds": "actual_rec_td",
        })
    )


def pbp_inputs() -> tuple[pl.DataFrame, pl.DataFrame]:
    pbp = pl.concat([
        pl.read_parquet(path) for path in sorted(CACHE.glob("nflverse_pbp_bonus_*.parquet"))
    ], how="diagonal_relaxed")
    ids = pl.read_parquet(CACHE / "nflverse_ff_playerids.parquet")
    bonus = aggregate_bonus_stats(pbp, ids).rename({"player_id": "sleeper_id"})
    attempts = (
        pbp.filter(
            (pl.col("down") == 4)
            & (pl.col("punt_attempt").fill_null(0) != 1)
            & (pl.col("field_goal_attempt").fill_null(0) != 1)
            & pl.col("posteam").is_not_null() & pl.col("defteam").is_not_null()
        )
        .with_columns(
            pl.col("posteam").map_elements(normalize_team, return_dtype=pl.String).alias("offense"),
            pl.col("defteam").map_elements(normalize_team, return_dtype=pl.String).alias("defense"),
        )
        .group_by("season", "week", "offense", "defense")
        .agg(
            pl.len().cast(pl.Float64).alias("attempts"),
            pl.col("fourth_down_failed").fill_null(0).sum().cast(pl.Float64).alias("stops"),
        )
    )
    return bonus, attempts


def build_frame() -> tuple[pl.DataFrame, pl.DataFrame]:
    base = pl.read_parquet(CACHE / "player_weeks.parquet")
    bonus, defense = pbp_inputs()
    frame = (
        base.join(projection_stats(), on=["sleeper_id", "season", "week"], how="left")
        .join(actual_stats(), on=["gsis_id", "season", "week"], how="left")
        .join(bonus, on=["sleeper_id", "season", "week"], how="left")
    )
    numeric = [
        *[f"proj_{c}" for c in PROJECTION_COLUMNS],
        "actual_pass_yd", "actual_rush_yd", "actual_rec_yd",
        "actual_pass_td", "actual_rush_td", "actual_rec_td", *BONUS_COLUMNS,
    ]
    return frame.with_columns(pl.col(column).fill_null(0.0) for column in numeric), defense


def within_week_spearman(frame: pl.DataFrame, prediction: str) -> float:
    values = []
    for week in sorted(frame.get_column("week").unique().to_list()):
        rows = frame.filter(pl.col("week") == week)
        if rows.height > 2:
            value = spearmanr(rows.get_column("act_pts"), rows.get_column(prediction)).statistic
            if np.isfinite(value):
                values.append(float(value))
    return float(np.mean(values))


def distribution_metrics(train: pl.DataFrame, test: pl.DataFrame, prediction: str) -> dict:
    renamed_train = train.with_columns(pl.col(prediction).alias("proj_pts"))
    renamed_test = test.with_columns(pl.col(prediction).alias("proj_pts"))
    model = QuantileModel.fit(renamed_train, k=500, smooth=9)
    totals = []
    coverages = {0.5: [], 0.8: [], 0.95: []}
    for position in POSITIONS:
        rows = renamed_test.filter(pl.col("pos") == position)
        if rows.is_empty() or position not in model.tables:
            continue
        actual = rows.get_column("act_pts").to_numpy()
        quantiles = model.quantile_matrix(position, rows.get_column("proj_pts").to_numpy())
        totals.append((float(pinball_crps(actual, quantiles, model.levels).mean()), rows.height))
        for nominal in coverages:
            low = int(np.argmin(np.abs(model.levels - (1 - nominal) / 2)))
            high = int(np.argmin(np.abs(model.levels - (1 + nominal) / 2)))
            coverages[nominal].append((coverage(actual, quantiles[:, low], quantiles[:, high]), rows.height))
    result = {"crps": sum(v * n for v, n in totals) / sum(n for _, n in totals)}
    for nominal, rows in coverages.items():
        result[f"coverage_{int(nominal * 100)}"] = sum(v * n for v, n in rows) / sum(n for _, n in rows)
    return result


def evaluate(frame: pl.DataFrame) -> tuple[dict, dict, int, bool, bool]:
    played = frame.filter(pl.col("played") & pl.col("season").is_in(TEST_SEASONS))
    summary = {}
    for season in TEST_SEASONS:
        rows = played.filter(pl.col("season") == season)
        train_end = 2025 if season == 2026 else season - 1
        train = frame.filter(pl.col("played") & (pl.col("season") <= train_end))
        base_error = rows.get_column("act_pts").to_numpy() - rows.get_column("proj_pts").to_numpy()
        bonus_error = rows.get_column("act_pts").to_numpy() - rows.get_column("proj_pts_bonus").to_numpy()
        summary[season] = {
            "n": rows.height,
            "base_mae": float(np.mean(np.abs(base_error))),
            "bonus_mae": float(np.mean(np.abs(bonus_error))),
            "base_bias": float(np.mean(base_error)),
            "bonus_bias": float(np.mean(bonus_error)),
            "base_spearman": within_week_spearman(rows, "proj_pts"),
            "bonus_spearman": within_week_spearman(rows, "proj_pts_bonus"),
            "base_distribution": distribution_metrics(train, rows, "proj_pts"),
            "bonus_distribution": distribution_metrics(train, rows, "proj_pts_bonus"),
        }
    position_bias = {}
    for position in POSITIONS:
        rows = played.filter(pl.col("pos") == position)
        position_bias[position] = {
            "n": rows.height,
            "base": float((rows.get_column("act_pts") - rows.get_column("proj_pts")).mean()),
            "bonus": float((rows.get_column("act_pts") - rows.get_column("proj_pts_bonus")).mean()),
        }
    bias_improved = sum(abs(row["bonus"]) < abs(row["base"]) for row in position_bias.values())
    mae_ok = all(row["bonus_mae"] <= row["base_mae"] * 1.005 for row in summary.values())
    spearman_ok = all(row["bonus_spearman"] >= row["base_spearman"] - 1e-9 for row in summary.values())
    adopted = mae_ok and bias_improved >= 5 and spearman_ok
    standard = (
        sum(row["bonus_mae"] <= row["base_mae"] * 0.99 for row in summary.values()) >= 3
        and all(row["bonus_mae"] <= row["base_mae"] * 1.01 for row in summary.values())
    )
    return summary, position_bias, bias_improved, adopted, standard


def bucket_bias(frame: pl.DataFrame) -> list[dict]:
    rows = []
    played = frame.filter(pl.col("played") & pl.col("season").is_in(TEST_SEASONS))
    for position in POSITIONS:
        for low, label in ((0.0, "low"), (8.0, "mid"), (16.0, "high")):
            selected = played.filter(
                (pl.col("pos") == position)
                & (pl.col("proj_pts") >= low)
                & ((pl.col("proj_pts") < low + 8) if low < 16 else pl.lit(True))
            )
            if selected.height:
                rows.append({
                    "position": position, "bucket": label, "n": selected.height,
                    "base": float((selected["act_pts"] - selected["proj_pts"]).mean()),
                    "bonus": float((selected["act_pts"] - selected["proj_pts_bonus"]).mean()),
                })
    return rows


def position_accuracy(frame: pl.DataFrame) -> list[dict]:
    rows = []
    played = frame.filter(pl.col("played") & pl.col("season").is_in(TEST_SEASONS))
    for position in POSITIONS:
        selected = played.filter(pl.col("pos") == position)
        if selected.is_empty():
            continue
        actual = selected.get_column("act_pts").to_numpy()
        base = selected.get_column("proj_pts").to_numpy()
        bonus = selected.get_column("proj_pts_bonus").to_numpy()
        rows.append({
            "position": position,
            "n": selected.height,
            "base_mae": float(np.mean(np.abs(actual - base))),
            "bonus_mae": float(np.mean(np.abs(actual - bonus))),
            "base_spearman": float(spearmanr(actual, base).statistic),
            "bonus_spearman": float(spearmanr(actual, bonus).statistic),
        })
    return rows


def write_report(frame, summary, position_bias, bias_improved, adopted, standard, mode):
    tested = frame.filter(pl.col("played") & pl.col("season").is_in(TEST_SEASONS))
    mean_highest = float(tested.get_column("expected_bonus_highest").mean())
    mean_stacked = float(tested.get_column("expected_bonus_stacked").mean())
    lines = [
        "# Expected-bonus projection", "",
        f"- Configured milestone mode: `{mode}`; both highest and stacked expectations were computed.",
        f"- Mean expected bonus on test rows: highest `{mean_highest:.3f}`, stacked `{mean_stacked:.3f}` points.",
        "- All estimates are walk-forward and use only earlier season-weeks.",
        f"- Task-specific adoption: {'ADOPTED' if adopted else 'REJECTED'}.",
        f"- Standard 1% rule: {'passed' if standard else 'failed'}.", "",
        "## Period metrics", "",
        "| Period | N | MAE base | MAE bonus | Change | Spearman base | Spearman bonus | CRPS base | CRPS bonus |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for season, row in summary.items():
        change = 100 * (row["base_mae"] - row["bonus_mae"]) / row["base_mae"]
        lines.append(
            f"| {season} | {row['n']} | {row['base_mae']:.4f} | {row['bonus_mae']:.4f} | "
            f"{change:+.3f}% | {row['base_spearman']:.5f} | {row['bonus_spearman']:.5f} | "
            f"{row['base_distribution']['crps']:.4f} | {row['bonus_distribution']['crps']:.4f} |"
        )
    lines.extend(["", f"Bias moved closer to zero in {bias_improved}/6 positions.", "", "## Position bias", "", "| Pos | N | Base | Bonus |", "|---|---:|---:|---:|"])
    for position, row in position_bias.items():
        lines.append(f"| {position} | {row['n']} | {row['base']:+.3f} | {row['bonus']:+.3f} |")
    lines.extend(["", "## Accuracy by position", "", "| Pos | N | MAE base | MAE bonus | Spearman base | Spearman bonus |", "|---|---:|---:|---:|---:|---:|"])
    for row in position_accuracy(frame):
        lines.append(
            f"| {row['position']} | {row['n']} | {row['base_mae']:.4f} | {row['bonus_mae']:.4f} | "
            f"{row['base_spearman']:.5f} | {row['bonus_spearman']:.5f} |"
        )
    lines.extend(["", "## Bias by projection bucket", "", "| Pos | Bucket | N | Base | Bonus |", "|---|---|---:|---:|---:|"])
    for row in bucket_bias(frame):
        lines.append(f"| {row['position']} | {row['bucket']} | {row['n']} | {row['base']:+.3f} | {row['bonus']:+.3f} |")
    lines.extend(["", "## Coverage diagnostics", "", "| Period | Projection | Cov50 | Cov80 | Cov95 |", "|---:|---|---:|---:|---:|"])
    for season, row in summary.items():
        for label, key in (("base", "base_distribution"), ("bonus", "bonus_distribution")):
            values = row[key]
            lines.append(f"| {season} | {label} | {values['coverage_50']:.3f} | {values['coverage_80']:.3f} | {values['coverage_95']:.3f} |")
    (ROOT / "reports/expected_bonus.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    frame, defense = build_frame()
    projected = walk_forward_bonus(frame, defense, config["scoring"])
    projected.write_parquet(CACHE / "projection_bonus_backtest.parquet")
    summary, position_bias, bias_improved, adopted, standard = evaluate(projected)
    write_report(
        projected, summary, position_bias, bias_improved, adopted, standard,
        config["scoring"].get("milestone_mode", "highest"),
    )
    print(json.dumps({
        "adopted": adopted, "standard_rule": standard,
        "bias_positions_improved": bias_improved,
        "periods": summary,
    }, indent=2))


if __name__ == "__main__":
    main()
