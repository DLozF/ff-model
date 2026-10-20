import json
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import norm

from ffm.backtest import coverage, pinball_crps, pit_histogram
from ffm.distributions import (
    POSITIONS,
    QuantileModel,
    apply_bias_scale,
    fit_bias_scale,
    previous_completed_weeks,
)

ROOT = Path("/opt/data/ff-model")
DATA = ROOT / "data/cache/player_weeks.parquet"
TEST_SEASONS = (2023, 2024, 2025, 2026)


def evaluate(model, train, test, season, adjusted=None):
    """Evaluate one rolling-origin season, optionally with adjusted quantiles."""
    results = []
    for position in POSITIONS:
        train_pos = train.filter((pl.col("pos") == position) & pl.col("played"))
        test_pos = test.filter((pl.col("pos") == position) & pl.col("played"))
        projection = test_pos.get_column("proj_pts").to_numpy()
        actual = test_pos.get_column("act_pts").to_numpy()
        if actual.size == 0 or position not in model.tables:
            continue
        quantiles = (
            adjusted[position]
            if adjusted is not None and position in adjusted
            else model.quantile_matrix(position, projection)
        )
        train_residual = (
            train_pos.get_column("act_pts").to_numpy()
            - train_pos.get_column("proj_pts").to_numpy()
        )
        test_residual = actual - projection
        sigma = float(np.std(train_residual, ddof=1))
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
            "residual_mean": float(np.mean(test_residual)),
            "residual_sd": float(np.std(test_residual, ddof=1)),
            "training_residual_sd": sigma,
        })
    return results


def backtest(frame, k, smooth):
    """Run rolling-season distribution backtests without weekly calibration."""
    results = []
    models = {}
    for season in TEST_SEASONS:
        train_end = 2025 if season == 2026 else season - 1
        train = frame.filter((pl.col("season") <= train_end) & pl.col("played"))
        test = frame.filter((pl.col("season") == season) & pl.col("played"))
        model = QuantileModel.fit(train, k=k, smooth=smooth)
        models[season] = model
        results.extend(evaluate(model, train, test, season))
    return results, models


def week6_base_comparison(final_frame):
    """Compare frozen 0f16eb9 metrics with the nflverse-rebuilt week 6 state."""
    frozen = json.loads(
        (ROOT / "models/p3_pre_week6_base_metrics.json").read_text(encoding="utf-8")
    )["rows"]
    train = final_frame.filter((pl.col("season") <= 2025) & pl.col("played"))
    model = QuantileModel.fit(train, k=500, smooth=9)
    rebuilt = evaluate(
        model,
        train,
        final_frame.filter((pl.col("season") == 2026) & pl.col("played")),
        2026,
    )
    return {"Before fix": frozen, "After rebuild": rebuilt}


def rolling_adjustment(frame, models):
    """Apply past-only eight-week per-position bias/spread calibration."""
    results = []
    parameter_log = []
    played = frame.filter(pl.col("played"))
    for season in TEST_SEASONS:
        train_end = 2025 if season == 2026 else season - 1
        train = played.filter(pl.col("season") <= train_end)
        test = played.filter(pl.col("season") == season)
        model = models[season]
        adjusted = {}
        for position in POSITIONS:
            position_test = test.filter(pl.col("pos") == position).sort("week", "sleeper_id")
            projection = position_test.get_column("proj_pts").to_numpy()
            base = model.quantile_matrix(position, projection)
            output = base.copy()
            test_weeks = position_test.get_column("week").to_numpy()
            position_history = played.filter(pl.col("pos") == position)
            for week in sorted(set(test_weeks.tolist())):
                prior_keys = previous_completed_weeks(position_history, season, int(week), window=8)
                if prior_keys:
                    history = position_history.join(
                        pl.DataFrame(
                            prior_keys,
                            schema={"season": pl.Int64, "week": pl.Int64},
                            orient="row",
                        ),
                        on=["season", "week"],
                        how="inner",
                    )
                else:
                    history = position_history.head(0)
                history_projection = history.get_column("proj_pts").to_numpy()
                history_actual = history.get_column("act_pts").to_numpy()
                history_quantiles = model.quantile_matrix(position, history_projection)
                fitted = fit_bias_scale(
                    history_projection,
                    history_actual,
                    history_quantiles,
                    model.levels,
                    model.tables[position].floor,
                    prior_weight=200,
                )
                selected = test_weeks == week
                output[selected] = apply_bias_scale(
                    projection[selected],
                    base[selected],
                    float(fitted["bias"]),
                    float(fitted["scale"]),
                    model.tables[position].floor,
                )
                parameter_log.append({
                    "test_season": season,
                    "test_week": int(week),
                    "pos": position,
                    "prior_weeks": [f"{s}-W{w}" for s, w in prior_keys],
                    **fitted,
                })
            adjusted[position] = output
        results.extend(evaluate(model, train, test, season, adjusted=adjusted))
    return results, parameter_log


def strict_coverage_passes(results):
    """Require every position-season coverage cell to be within three points."""
    return all(
        abs(row["coverage_50"] - 0.50) <= 0.03
        and abs(row["coverage_80"] - 0.80) <= 0.03
        and abs(row["coverage_95"] - 0.95) <= 0.03
        for row in results
    )


def season_crps(results):
    """Return sample-weighted CRPS by test season."""
    output = {}
    for season in TEST_SEASONS:
        rows = [row for row in results if row["season"] == season]
        total = sum(row["n"] for row in rows)
        output[season] = sum(row["crps"] * row["n"] for row in rows) / total
    return output


def write_report(primary, retry, before, after, adopted, improved_seasons, week6_comparison):
    """Write baseline diagnostics and rolling-calibration comparison."""
    before_by_key = {(row["season"], row["pos"]): row for row in before}
    lines = [
        "# Distribution calibration",
        "",
        "## Decision",
        "",
        "- Base model for the rolling candidate: K=500, smoothing=9 (required retry).",
        "- Rolling fit: per position and test week, CRPS-fit `b` and `s` on only the previous eight completed weeks; shrink toward `b=0`, `s=1` by `n/(n+200)`.",
        f"- Strict coverage gate (every position-season interval within 3 points): {'pass' if strict_coverage_passes(after) else 'fail'}.",
        f"- Test seasons with lower sample-weighted CRPS: {improved_seasons}/4.",
        f"- Rolling calibration adopted: {'yes' if adopted else 'no'}.",
        "",
        "## Base-model 2026 impact of week 6 handling",
        "",
        "The same K=500/smoothing=9 base model fit on 2021-2025 is used for all states.",
        "",
        "| Pos | Cov50 before | Cov80 before | Cov95 before | CRPS before | Cov50 after | Cov80 after | Cov95 after | CRPS after |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    comparison_maps = {
        label: {row["pos"]: row for row in rows}
        for label, rows in week6_comparison.items()
    }
    for position in POSITIONS:
        zero = comparison_maps["Before fix"][position]
        rebuilt = comparison_maps["After rebuild"][position]
        lines.append(
            f"| {position} | {zero['coverage_50']:.3f} | {zero['coverage_80']:.3f} | "
            f"{zero['coverage_95']:.3f} | {zero['crps']:.3f} | "
            f"{rebuilt['coverage_50']:.3f} | {rebuilt['coverage_80']:.3f} | "
            f"{rebuilt['coverage_95']:.3f} | {rebuilt['crps']:.3f} |"
        )
    lines.extend([
        "",
        "## Before/after by position and season",
        "",
        "| Season | Pos | N | Cov50 before | Cov50 after | Cov80 before | Cov80 after | Cov95 before | Cov95 after | CRPS before | CRPS after |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in after:
        old = before_by_key[(row["season"], row["pos"])]
        lines.append(
            f"| {row['season']} | {row['pos']} | {row['n']} | "
            f"{old['coverage_50']:.3f} | {row['coverage_50']:.3f} | "
            f"{old['coverage_80']:.3f} | {row['coverage_80']:.3f} | "
            f"{old['coverage_95']:.3f} | {row['coverage_95']:.3f} | "
            f"{old['crps']:.3f} | {row['crps']:.3f} |"
        )
    lines.extend([
        "",
        "## 2026 residual diagnostics",
        "",
        "Residual is actual minus projection. Training SD uses played rows from seasons 2021-2025.",
        "",
        "| Pos | N | Mean residual | 2026 residual SD | Training residual SD | SD ratio |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for row in before:
        if row["season"] != 2026:
            continue
        ratio = row["residual_sd"] / row["training_residual_sd"]
        lines.append(
            f"| {row['pos']} | {row['n']} | {row['residual_mean']:.3f} | "
            f"{row['residual_sd']:.3f} | {row['training_residual_sd']:.3f} | {ratio:.3f} |"
        )
    for label, rows in (("Primary baseline: K=300, smoothing=5", primary), ("Required retry baseline: K=500, smoothing=9", retry)):
        lines.extend([
            "",
            f"## {label}",
            "",
            "| Season | Pos | N | Cov50 | Cov80 | Cov95 | CRPS | Normal CRPS |",
            "|---:|---|---:|---:|---:|---:|---:|---:|",
        ])
        for row in rows:
            lines.append(
                f"| {row['season']} | {row['pos']} | {row['n']} | "
                f"{row['coverage_50']:.3f} | {row['coverage_80']:.3f} | {row['coverage_95']:.3f} | "
                f"{row['crps']:.3f} | {row['normal_crps']:.3f} |"
            )
    (ROOT / "reports/calibration.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    frame = pl.read_parquet(DATA)
    comparison = week6_base_comparison(frame)
    primary, _ = backtest(frame, 300, 5)
    retry, retry_models = backtest(frame, 500, 9)
    adjusted, parameter_log = rolling_adjustment(frame, retry_models)
    before_crps = season_crps(retry)
    after_crps = season_crps(adjusted)
    improved = sum(after_crps[season] < before_crps[season] for season in TEST_SEASONS)
    adopted = strict_coverage_passes(adjusted) and improved >= 3

    final_model = QuantileModel.fit(frame.filter(pl.col("played")), k=500, smooth=9)
    final_model.save(ROOT / "models/quantiles_2026.npz")
    (ROOT / "logs/p3-rolling-parameters.json").write_text(
        json.dumps(parameter_log, indent=2, allow_nan=False), encoding="utf-8"
    )
    write_report(primary, retry, retry, adjusted, adopted, improved, comparison)

    print(f"rolling calibration adopted: {adopted}")
    print(f"strict coverage gate: {strict_coverage_passes(adjusted)}")
    for season in TEST_SEASONS:
        print(
            f"{season} CRPS {before_crps[season]:.6f} -> {after_crps[season]:.6f} "
            f"improved={after_crps[season] < before_crps[season]}"
        )


if __name__ == "__main__":
    main()
