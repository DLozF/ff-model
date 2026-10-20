import json
from pathlib import Path

import numpy as np
import polars as pl
import yaml

from ffm.backtest import pinball_crps
from ffm.distributions import POSITIONS, QuantileModel
from ffm.experiments import fit_through_origin, lagged_residual_feature, rolling_origin_split

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"


def mean_crps(model, test):
    """Compute row-weighted CRPS across all modeled positions."""
    scores = []
    for position in POSITIONS:
        rows = test.filter((pl.col("pos") == position) & pl.col("played"))
        if rows.is_empty():
            continue
        quantiles = model.quantile_matrix(position, rows.get_column("proj_pts").to_numpy())
        scores.extend(pinball_crps(
            rows.get_column("act_pts").to_numpy(), quantiles, model.levels
        ))
    return float(np.mean(scores))


def baseline_result(frame, season):
    train, test = rolling_origin_split(frame.filter(pl.col("played")), season)
    model = QuantileModel.fit(train, k=500, smooth=9)
    return mean_crps(model, test)


def slow_consensus(frame, season):
    featured = lagged_residual_feature(frame)
    train, test = rolling_origin_split(featured.filter(pl.col("played")), season)
    x = np.clip(train.get_column("residual_last3").fill_null(0).to_numpy(), -3, 3)
    target = train.get_column("residual").to_numpy()
    coefficient = fit_through_origin(x, target)
    train = train.with_columns(
        (pl.col("proj_pts") + coefficient * pl.col("residual_last3").fill_null(0).clip(-3, 3)).alias("proj_pts")
    )
    test = test.with_columns(
        (pl.col("proj_pts") + coefficient * pl.col("residual_last3").fill_null(0).clip(-3, 3)).alias("proj_pts")
    )
    model = QuantileModel.fit(train, k=500, smooth=9)
    return mean_crps(model, test), coefficient


def qb_efficiency_feature(frame, stats):
    """Join past-only four-game QB EPA/dropback to player weeks."""
    qb = (
        stats.filter((pl.col("position") == "QB") & (pl.col("season_type") == "REG"))
        .group_by("season", "week", "team")
        .agg(pl.col("passing_epa").sum(), pl.col("attempts").sum(), pl.col("sacks_suffered").sum())
        .with_columns(
            (pl.col("passing_epa") / (pl.col("attempts") + pl.col("sacks_suffered"))).alias("qb_epa_dropback")
        )
        .sort("season", "team", "week")
        .with_columns(
            pl.col("qb_epa_dropback").shift(1).rolling_mean(4, min_samples=1)
            .over("season", "team").alias("qb_epa_last4")
        )
        .select("season", "week", "team", "qb_epa_last4")
    )
    return frame.join(qb, on=["season", "week", "team"], how="left")


def qb_efficiency(frame, stats, season):
    featured = qb_efficiency_feature(frame, stats)
    train, test = rolling_origin_split(featured.filter(pl.col("played")), season)
    source = train.filter(pl.col("pos").is_in(["WR", "TE"])).get_column("qb_epa_last4").drop_nulls()
    mean = float(source.mean())
    std = float(source.std())
    coefficients = {}
    adjusted_train = train
    adjusted_test = test
    for position in ("WR", "TE"):
        position_train = train.filter(pl.col("pos") == position)
        feature = ((position_train.get_column("qb_epa_last4").fill_null(mean).to_numpy() - mean) / std)
        target = (
            position_train.get_column("act_pts").to_numpy()
            - position_train.get_column("proj_pts").to_numpy()
        )
        coefficient = fit_through_origin(feature, target)
        coefficients[position] = coefficient
        adjusted_train = adjusted_train.with_columns(
            pl.when(pl.col("pos") == position)
            .then(pl.col("proj_pts") + coefficient * (pl.col("qb_epa_last4").fill_null(mean) - mean) / std)
            .otherwise(pl.col("proj_pts")).alias("proj_pts")
        )
        adjusted_test = adjusted_test.with_columns(
            pl.when(pl.col("pos") == position)
            .then(pl.col("proj_pts") + coefficient * (pl.col("qb_epa_last4").fill_null(mean) - mean) / std)
            .otherwise(pl.col("proj_pts")).alias("proj_pts")
        )
    model = QuantileModel.fit(adjusted_train, k=500, smooth=9)
    return mean_crps(model, adjusted_test), coefficients


def main():
    frame = pl.read_parquet(CACHE / "player_weeks.parquet")
    stats = pl.read_parquet(CACHE / "nflverse_player_stats.parquet")
    results = {"E1 slow consensus": [], "E2 QB efficiency": []}
    for season in (2023, 2024, 2025):
        baseline = baseline_result(frame, season)
        e1, k = slow_consensus(frame, season)
        e2, coefficients = qb_efficiency(frame, stats, season)
        results["E1 slow consensus"].append({
            "season": season, "baseline": baseline, "experiment": e1,
            "improvement": (baseline - e1) / baseline, "coefficient": k,
        })
        results["E2 QB efficiency"].append({
            "season": season, "baseline": baseline, "experiment": e2,
            "improvement": (baseline - e2) / baseline, "coefficients": coefficients,
        })
    adopted = {
        name: sum(row["improvement"] >= 0.01 for row in rows) >= 2
        for name, rows in results.items()
    }
    lines = [
        "# Experiments", "",
        "Adoption rule: at least 1% out-of-sample CRPS improvement in at least two of three test seasons.", "",
    ]
    for name, rows in results.items():
        lines.extend([
            f"## {name}", "", f"Adopted: {'yes' if adopted[name] else 'no'}", "",
            "| Season | Baseline CRPS | Experiment CRPS | Improvement | Fitted coefficient(s) |",
            "|---:|---:|---:|---:|---|",
        ])
        for row in rows:
            coefficient = row.get("coefficient", row.get("coefficients"))
            lines.append(
                f"| {row['season']} | {row['baseline']:.6f} | {row['experiment']:.6f} | "
                f"{row['improvement']:.3%} | `{json.dumps(coefficient, sort_keys=True)}` |"
            )
        lines.append("")
    lines.extend([
        "## E3 Matchup", "",
        "Skipped: Sleeper future-week projections were available for every remaining 2026 week through week 18.", "",
    ])
    (ROOT / "reports/experiments.md").write_text("\n".join(lines), encoding="utf-8")
    config_path = ROOT / "config.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["experiments"] = {
        "slow_consensus": adopted["E1 slow consensus"],
        "qb_efficiency": adopted["E2 QB efficiency"],
        "matchup": False,
    }
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    for name, rows in results.items():
        print(name, "adopted", adopted[name], "improvements", [round(row["improvement"], 6) for row in rows])


if __name__ == "__main__":
    main()
