import numpy as np

from ffm.trade import fragility_label, metric_delta, roster_lineup_points, stress_worlds, trade_verdict


def test_metric_delta_zero_is_exact():
    values = np.array([0.0, 1.0, 1.0, 0.0])
    result = metric_delta(values, values)
    assert result == {"mean": 0.0, "se": 0.0, "low": 0.0, "high": 0.0}


def test_clone_trade_has_no_clear_effect():
    points = np.array([[[10.0, 10.0], [20.0, 20.0]]])
    projections = points.copy()
    available = np.ones_like(points, dtype=bool)
    positions = np.array(["WR", "WR"])
    before = roster_lineup_points(points, projections, available, positions, [0]).ravel()
    after = roster_lineup_points(points, projections, available, positions, [1]).ravel()
    interval = metric_delta(before, after)
    assert trade_verdict(interval) == "NO CLEAR EFFECT"


def test_positive_interval_is_accept():
    assert trade_verdict({"low": 0.01, "high": 0.03}) == "ACCEPT"
    assert trade_verdict({"low": -0.03, "high": -0.01}) == "DECLINE"


def test_stress_worlds_widens_scores_and_thins_only_qb_availability():
    points = np.array([[[8.0, 4.0], [10.0, 6.0], [12.0, 8.0], [14.0, 10.0]]])
    available = np.ones_like(points, dtype=bool)
    positions = np.array(["QB", "WR"])

    stressed_points, stressed_available = stress_worlds(points, available, positions)

    assert np.isclose(stressed_points[0, :, 1].std(), 1.25 * points[0, :, 1].std())
    assert stressed_available[0, :, 0].sum() < available[0, :, 0].sum()
    assert np.array_equal(stressed_available[0, :, 1], available[0, :, 1])


def test_fragility_label_names_changed_verdict():
    assert fragility_label("ACCEPT", "NO CLEAR EFFECT") == (
        "FRAGILE", "stress verdict changed from ACCEPT to NO CLEAR EFFECT"
    )
    assert fragility_label("ACCEPT", "ACCEPT") == ("ROBUST", "stress verdict unchanged")
