import numpy as np
import polars as pl

from ffm.own_projection import build_features, ewma, fit_half_life


def test_ewma_recent_points_weight_more():
    assert ewma(np.array([0.0, 10.0]), 0.5) > ewma(np.array([0.0, 10.0]), 4.0)
    assert ewma(np.array([10.0, 0.0]), 0.5) < ewma(np.array([10.0, 0.0]), 4.0)
    assert ewma(np.array([]), 2.0) == 0.0


def test_fit_half_life_returns_per_position_values():
    frame = pl.DataFrame({
        "season": [2022, 2022, 2022], "week": [1, 2, 3], "pos": ["QB", "QB", "QB"],
        "sleeper_id": ["a", "a", "a"], "act_pts": [10.0, 20.0, 5.0],
    })

    half_lives = fit_half_life(frame)

    assert half_lives["QB"] in (1.0, 2.0, 3.0, 4.0, 6.0, 8.0)


def test_build_features_never_uses_same_week_data():
    frame = pl.DataFrame({
        "season": [2023, 2023], "week": [1, 2], "sleeper_id": ["a", "a"], "pos": ["QB", "QB"],
        "team": ["TB", "TB"], "act_pts": [10.0, 30.0], "proj_pts": [15.0, 18.0],
        "played": [True, True],
    })

    features = build_features(frame)

    week2 = features.filter(pl.col("week") == 2)
    assert week2.item(0, "ewma") > 0.0
    assert week2.item(0, "last3") == 10.0
    week1 = features.filter(pl.col("week") == 1)
    assert week1.item(0, "last3") == 0.0
