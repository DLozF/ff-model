import numpy as np

from ffm.backtest import coverage, matchup_metrics, pinball_crps, pit_histogram


def test_pinball_crps_is_zero_for_exact_quantiles():
    levels = np.array([0.25, 0.5, 0.75])
    quantiles = np.array([[2.0, 2.0, 2.0]])
    assert pinball_crps(np.array([2.0]), quantiles, levels)[0] == 0


def test_coverage_and_pit_histogram():
    actual = np.array([1.0, 2.0, 3.0, 10.0])
    lower = np.array([0.0, 1.0, 2.0, 4.0])
    upper = np.array([2.0, 3.0, 4.0, 8.0])
    assert coverage(actual, lower, upper) == 0.75

    quantiles = np.tile(np.arange(1, 200), (4, 1))
    histogram = pit_histogram(actual, quantiles)
    assert histogram.sum() == 4
    assert histogram.shape == (10,)


def test_matchup_metrics_are_exact_for_perfect_predictions():
    result = matchup_metrics(np.array([0.0, 1.0]), np.array([0.0, 1.0]))
    assert result["brier"] == 0
    assert result["log_loss"] < 1e-10
    assert sum(row["n"] for row in result["calibration"]) == 2
