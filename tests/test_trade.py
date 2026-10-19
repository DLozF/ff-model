import numpy as np

from ffm.trade import metric_delta, roster_lineup_points, trade_verdict


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
