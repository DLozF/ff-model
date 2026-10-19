from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import norm

from ffm.backtest import coverage, pinball_crps, pit_histogram
from ffm.distributions import POSITIONS, QuantileModel

ROOT = Path("/opt/data/ff-model")
DATA = ROOT / "data/cache/player_weeks.parquet"


def evaluate(model, train, test, season):
    """Evaluate one rolling-origin season."""
    results = []
    for position in POSITIONS:
        train_pos = train.filter((pl.col("pos") == position) & pl.col("played"))
        test_pos = test.filter((pl.col("pos") == position) & pl.col("played"))
        projection = test_pos.get_column("proj_pts").to_numpy()
        actual = test_pos.get_column("act_pts").to_numpy()
        if actual.size == 0 or position not in model.tables:
            continue
        quantiles = model.quantile_matrix(position, projection)
        residual = (
            train_pos.get_column("act_pts").to_numpy()
            - train_pos.get_column("proj_pts").to_numpy()
        )
        sigma = float(np.std(residual, ddof=1))
        normal_quantiles = projection[:, None] + sigma * norm.ppf(model.levels)[None, :]
        coverages = {}
        for nominal in (0.50, 0.80, 0.95):
            low_level = (1 - nominal) / 2
            high_level = 1 - low_level
            low = np.argmin(np.abs(model.levels - low_level))
            high = np.argmin(np.abs(model.levels - high_level))
            coverages[nominal] = coverage(actual, quantiles[:, low], quantiles[:, high])
        results.append({
            "season": season,
            "pos": position,
            "n": actual.size,
            "mae_median": float(np.mean(np.abs(quantiles[:, 99] - actual))),
            "coverage_50": coverages[0.50],
            "coverage_80": coverages[0.80],
            "coverage_95": coverages[0.95],
            "crps": float(pinball_crps(actual, quantiles, model.levels).mean()),
            "normal_crps": float(pinball_crps(actual, normal_quantiles, model.levels).mean()),
            "pit": pit_histogram(actual, quantiles).tolist(),
        })
    return results


def backtest(frame, k, smooth):
    """Run rolling season distribution backtests."""
    results = []
    for season in (2023, 2024, 2025, 2026):
        train_end = 2025 if season == 2026 else season - 1
        train = frame.filter((pl.col("season") <= train_end) & pl.col("played"))
        test = frame.filter((pl.col("season") == season) & pl.col("played"))
        model = QuantileModel.fit(train, k=k, smooth=smooth)
        results.extend(evaluate(model, train, test, season))
    return results


def passes(results):
    """Check the phase calibration and CRPS criteria."""
    return all(
        abs(row["coverage_50"] - 0.50) <= 0.03
        and abs(row["coverage_80"] - 0.80) <= 0.03
        and abs(row["coverage_95"] - 0.95) <= 0.03
        and row["crps"] < row["normal_crps"]
        for row in results
    )


def write_report(attempts, chosen, passed):
    """Write the calibration report."""
    lines = [
        "# Distribution calibration",
        "",
        f"Chosen fit: K={chosen[0]}, smoothing={chosen[1]}",
        f"All DONE WHEN criteria passed: {'yes' if passed else 'no'}",
        "",
    ]
    for label, settings, results in attempts:
        lines.extend([
            f"## {label}: K={settings[0]}, smoothing={settings[1]}",
            "",
            "| Season | Pos | N | MAE median | Cov 50 | Cov 80 | Cov 95 | CRPS | Normal CRPS | PIT bins |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ])
        for row in results:
            lines.append(
                f"| {row['season']} | {row['pos']} | {row['n']} | {row['mae_median']:.3f} | "
                f"{row['coverage_50']:.3f} | {row['coverage_80']:.3f} | {row['coverage_95']:.3f} | "
                f"{row['crps']:.3f} | {row['normal_crps']:.3f} | {row['pit']} |"
            )
        lines.append("")
    (ROOT / "reports/calibration.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    frame = pl.read_parquet(DATA)
    primary = backtest(frame, 300, 5)
    attempts = [("Primary", (300, 5), primary)]
    chosen = (300, 5)
    final_results = primary
    if not passes(primary):
        retry = backtest(frame, 500, 9)
        attempts.append(("Required retry", (500, 9), retry))
        chosen = (500, 9)
        final_results = retry
    passed = passes(final_results)
    final_model = QuantileModel.fit(frame.filter(pl.col("played")), k=chosen[0], smooth=chosen[1])
    final_model.save(ROOT / "models/quantiles_2026.npz")
    write_report(attempts, chosen, passed)
    print(f"chosen K={chosen[0]} smooth={chosen[1]}")
    print(f"criteria passed: {passed}")
    for row in final_results:
        failures = []
        for nominal in (50, 80, 95):
            if abs(row[f"coverage_{nominal}"] - nominal / 100) > 0.03:
                failures.append(f"cov{nominal}={row[f'coverage_{nominal}']:.3f}")
        if row["crps"] >= row["normal_crps"]:
            failures.append(f"crps={row['crps']:.3f}>={row['normal_crps']:.3f}")
        if failures:
            print(row["season"], row["pos"], ", ".join(failures))


if __name__ == "__main__":
    main()
