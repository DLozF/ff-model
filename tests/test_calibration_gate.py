import numpy as np

from ffm.backtest import matchup_metrics, wilson_interval, ece_bootstrap


def test_wilson_interval_covers_noisy_small_bin():
    low, high = wilson_interval(360, 1 - 0.065119)

    assert low <= 0.935 <= high


def test_ece_bootstrap_interval_is_deterministic():
    rng = np.random.default_rng(2026)
    probability = rng.uniform(0, 1, 1000)
    outcome = (rng.uniform(0, 1, 1000) < probability).astype(float)

    first = ece_bootstrap(probability, outcome, seed=2026)
    second = ece_bootstrap(probability, outcome, seed=2026)

    assert first == second
    assert first["low"] <= first["mean"] <= first["high"]


def test_matchup_metrics_returns_per_bin_counts():
    probability = np.array([0.1, 0.2, 0.3, 0.4])
    outcome = np.array([0.0, 0.0, 1.0, 1.0])

    metrics = matchup_metrics(probability, outcome)

    assert sum(row["n"] for row in metrics["calibration"]) == 4
