"""Evaluate the preregistered expanded pregame ridge model."""
import json
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import spearmanr

from ffm.backtest_projection import TEST_SEASONS, walk_forward_expanded
from ffm.own_projection import build_context_features

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"


def within_week_spearman(frame: pl.DataFrame, prediction: str) -> float:
    values = []
    for week in sorted(frame.get_column("week").unique().to_list()):
        rows = frame.filter(pl.col("week") == week)
        if rows.height < 3:
            continue
        value = spearmanr(rows.get_column("act_pts"), rows.get_column(prediction)).statistic
        if np.isfinite(value):
            values.append(float(value))
    return float(np.mean(values))


def metrics(frame: pl.DataFrame, prediction: str) -> dict:
    actual = frame.get_column("act_pts").to_numpy()
    projected = frame.get_column(prediction).to_numpy()
    error = actual - projected
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
        "bias": float(np.mean(error)),
        "spearman": within_week_spearman(frame, prediction),
    }


def evaluate(predictions: pl.DataFrame) -> tuple[dict, bool]:
    periods = {}
    for season in TEST_SEASONS:
        rows = predictions.filter(pl.col("season") == season)
        periods[season] = {
            "n": rows.height,
            "baseline": metrics(rows, "proj_pts"),
            "ridge": metrics(rows, "expanded_ridge"),
        }
    improved = sum(
        row["ridge"]["mae"] <= row["baseline"]["mae"] * 0.99
        for row in periods.values()
    )
    adopted = (
        improved >= 3
        and all(row["ridge"]["mae"] <= row["baseline"]["mae"] * 1.01 for row in periods.values())
        and all(row["ridge"]["spearman"] >= row["baseline"]["spearman"] for row in periods.values())
    )
    return periods, adopted


def position_metrics(predictions: pl.DataFrame) -> list[dict]:
    output = []
    for position in sorted(predictions.get_column("pos").unique().to_list()):
        rows = predictions.filter(pl.col("pos") == position)
        output.append({
            "position": position,
            "n": rows.height,
            "baseline": metrics(rows, "proj_pts"),
            "ridge": metrics(rows, "expanded_ridge"),
        })
    return output


def write_report(periods: dict, positions: list[dict], adopted: bool) -> None:
    lines = [
        "# Expanded own-model features", "",
        "- Baseline: Sleeper projection (`projection_source` remained `sleeper` after T04-5).",
        "- Model: standardized per-position ridge, alpha 1.0, seed 2026, walk-forward.",
        "- Features: Sleeper, last-3, season average, EWMA, snap/target/carry shares, implied points, spread, opponent points allowed, home, and QB change.",
        "- All feature histories and training rows are strictly before each predicted week.",
        f"- Standard adoption rule: {'ADOPTED' if adopted else 'REJECTED'}.", "",
        "## Period metrics", "",
        "| Period | N | MAE base | MAE ridge | Improvement | Spearman base | Spearman ridge | RMSE base | RMSE ridge | Bias base | Bias ridge |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for season, row in periods.items():
        base, ridge = row["baseline"], row["ridge"]
        gain = 100 * (base["mae"] - ridge["mae"]) / base["mae"]
        lines.append(
            f"| {season} | {row['n']} | {base['mae']:.4f} | {ridge['mae']:.4f} | {gain:+.3f}% | "
            f"{base['spearman']:.5f} | {ridge['spearman']:.5f} | {base['rmse']:.4f} | {ridge['rmse']:.4f} | "
            f"{base['bias']:+.3f} | {ridge['bias']:+.3f} |"
        )
    lines.extend(["", "## Position metrics", "", "| Pos | N | MAE base | MAE ridge | Spearman base | Spearman ridge |", "|---|---:|---:|---:|---:|---:|"])
    for row in positions:
        lines.append(
            f"| {row['position']} | {row['n']} | {row['baseline']['mae']:.4f} | {row['ridge']['mae']:.4f} | "
            f"{row['baseline']['spearman']:.5f} | {row['ridge']['spearman']:.5f} |"
        )
    lines.extend(["", "HistGradientBoostingRegressor was not run because ridge failed the standard adoption rule; the task directs stopping when the gate is not met."] if not adopted else [])
    (ROOT / "reports/own_model_expanded.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    frame = pl.read_parquet(CACHE / "player_weeks.parquet")
    stats = pl.read_parquet(CACHE / "nflverse_player_stats.parquet")
    snaps = pl.read_parquet(CACHE / "nflverse_snap_counts.parquet")
    mapping = pl.read_parquet(CACHE / "nflverse_ff_playerids.parquet")
    schedules = pl.read_parquet(CACHE / "nflverse_schedules.parquet")
    features = build_context_features(frame, stats, snaps, mapping, schedules)
    predictions = walk_forward_expanded(features)
    predictions.write_parquet(CACHE / "expanded_projection_backtest.parquet")
    periods, adopted = evaluate(predictions)
    positions = position_metrics(predictions)
    write_report(periods, positions, adopted)
    print(json.dumps({"adopted": adopted, "periods": periods}, indent=2))


if __name__ == "__main__":
    main()
