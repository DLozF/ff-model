"""Build reports/projection_scorecard.md from the Task 02 walk-forward backtest."""
import json
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import spearmanr

from ffm.backtest import pinball_crps
from ffm.distributions import QuantileModel

ROOT = Path("/opt/data/ff-model")
PREDICTORS = ("proj_pts", "last3", "season_avg", "own", "blended")
LABELS = {
    "proj_pts": "B0 Sleeper projection",
    "last3": "B1 last-3-game average",
    "season_avg": "B2 season-to-date average",
    "own": "B3 own model",
    "blended": "B4 blend",
}
TEST_SEASONS = (2023, 2024, 2025, 2026)
SEED = 2026


def within_week_spearman(frame: pl.DataFrame, prediction: str) -> float:
    """Average the within-week rank correlation across every test week."""
    correlations = []
    for week in sorted(frame.get_column("week").unique().to_list()):
        rows = frame.filter(pl.col("week") == week)
        if rows.height > 2:
            value = spearmanr(rows.get_column("act_pts"), rows.get_column(prediction)).statistic
            if not np.isnan(value):
                correlations.append(value)
    return float(np.mean(correlations)) if correlations else float("nan")


def position_crps(frame: pl.DataFrame, prediction: str, model: QuantileModel) -> float:
    """Sample-weighted CRPS after passing predictions through the quantile model."""
    totals = []
    for position in model.tables:
        rows = frame.filter(pl.col("pos") == position)
        if rows.is_empty():
            continue
        quantiles = model.quantile_matrix(position, rows.get_column(prediction).to_numpy())
        crps = pinball_crps(rows.get_column("act_pts").to_numpy(), quantiles, model.levels).mean()
        totals.append((float(crps), rows.height))
    return sum(crps * count for crps, count in totals) / sum(count for _, count in totals)


def write_scorecard(predictions: pl.DataFrame) -> dict:
    """Assemble the per-period metric table and adoption decision."""
    model = QuantileModel.load(ROOT / "models/quantiles_2026.npz")
    summary = {}
    for season in TEST_SEASONS:
        rows = predictions.filter(pl.col("season") == season)
        summary[season] = {}
        for prediction in PREDICTORS:
            errors = rows.get_column("act_pts").to_numpy() - rows.get_column(prediction).to_numpy()
            summary[season][prediction] = {
                "mae": float(np.mean(np.abs(errors))),
                "rmse": float(np.sqrt(np.mean(np.square(errors)))),
                "bias": float(np.mean(errors)),
                "spearman": within_week_spearman(rows, prediction),
                "crps": position_crps(rows, prediction, model),
            }
    lines = [
        "# Projection scorecard", "",
        f"Determinism seed: {SEED}. Predictions: `data/cache/projection_backtest.parquet`.",
        "",
        "| Season | Predictor | MAE | RMSE | Bias | Spearman | CRPS |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for season in TEST_SEASONS:
        for prediction in PREDICTORS:
            row = summary[season][prediction]
            lines.append(
                f"| {season} | {LABELS[prediction]} | {row['mae']:.3f} | {row['rmse']:.3f} | "
                f"{row['bias']:+.3f} | {row['spearman']:.4f} | {row['crps']:.3f} |"
            )
    improved = sum(
        summary[season]["blended"]["mae"] < summary[season]["proj_pts"]["mae"] * 0.99
        for season in TEST_SEASONS
    )
    not_worse = all(
        summary[season]["blended"]["mae"] >= summary[season]["proj_pts"]["mae"] * 1.01 is False
        or summary[season]["blended"]["mae"] <= summary[season]["proj_pts"]["mae"] * 1.01
        for season in TEST_SEASONS
    )
    spearman_ok = all(
        summary[season]["blended"]["spearman"] >= summary[season]["proj_pts"]["spearman"] - 1e-9
        for season in TEST_SEASONS
    )
    adopted = improved >= 3 and not_worse and spearman_ok
    lines.extend([
        "",
        "## Decision",
        "",
        f"- Seasons meeting the 1% MAE improvement threshold: {improved}/4.",
        f"- No period worse by more than 1%: {'yes' if not_worse else 'no'}.",
        f"- Spearman not worse in any period: {'yes' if spearman_ok else 'no'}.",
        f"- Adopted: {'yes' if adopted else 'no'}.",
        "",
        "## Error analysis patterns",
        "",
    ])
    (ROOT / "reports/projection_scorecard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"summary": summary, "adopted": adopted, "improved": improved}


def largest_misses(predictions: pl.DataFrame, count: int = 50) -> pl.DataFrame:
    """Rank the biggest 2026 misses by absolute error."""
    rows = predictions.filter(pl.col("season") == 2026).with_columns(
        (pl.col("act_pts") - pl.col("blended")).abs().alias("abs_error")
    ).sort("abs_error", descending=True)
    return rows.head(count)


def main() -> None:
    predictions = pl.read_parquet(ROOT / "data/cache/projection_backtest.parquet")
    result = write_scorecard(predictions)
    misses = largest_misses(predictions)
    misses.select("season", "week", "sleeper_id", "pos", "proj_pts", "blended", "act_pts").write_csv(
        ROOT / "logs/task02-largest-misses.csv"
    )
    bias = {}
    for position in ("QB", "RB", "WR", "TE", "K", "DEF"):
        rows = predictions.filter(pl.col("pos") == position)
        for bucket, label in ((0.0, "low"), (8.0, "mid"), (16.0, "high")):
            subset = rows.filter(
                pl.col("proj_pts").is_between(bucket, bucket + 8.0, closed="left") if bucket < 16 else pl.col("proj_pts") >= bucket
            )
            if subset.height:
                bias[f"{position}_{label}"] = round(
                    float((subset.get_column("act_pts") - subset.get_column("proj_pts")).mean()), 3
                )
    lines = (ROOT / "reports/projection_scorecard.md").read_text().splitlines()
    lines.append("")
    lines.append("| Position bucket | Sleeper bias (actual - projection) |")
    lines.append("|---|---:|")
    for key, value in bias.items():
        lines.append(f"| {key} | {value:+.3f} |")
    lines.append("")
    lines.append("## Largest 50 misses (2026, blend prediction)")
    lines.append("")
    lines.append("See `logs/task02-largest-misses.csv` for the full list; causes come from Part A tagging.")
    lines.append("")
    named = misses.join(
        pl.read_parquet(ROOT / "data/cache/sleeper_players.parquet").select(
            pl.col("player_id").cast(pl.String).alias("sleeper_id"),
            pl.col("full_name").alias("name"),
        ),
        on="sleeper_id",
        how="left",
    )
    lines.append("| Name | Pos | Week | Projection | Blend | Actual | Abs error |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for row in named.iter_rows(named=True):
        lines.append(
            f"| {row['name']} | {row['pos']} | {row['week']} | {row['proj_pts']:.2f} | "
            f"{row['blended']:.2f} | {row['act_pts']:.2f} | {row['abs_error']:.2f} |"
        )
    (ROOT / "reports/projection_scorecard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"adopted": result["adopted"], "improved": result["improved"]}))


if __name__ == "__main__":
    main()
