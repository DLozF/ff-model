import numpy as np
import polars as pl

from ffm.backtest_projection import blend_weight, train_ridge, walk_forward
from ffm.own_projection import build_features


def test_train_ridge_predicts_close_on_linear_data():
    frame = pl.DataFrame({
        "pos": ["QB"] * 120,
        "proj_pts": np.linspace(0, 30, 120),
        "last3": np.linspace(0, 30, 120),
        "season_avg": np.linspace(0, 30, 120),
        "ewma": np.linspace(0, 30, 120),
        "act_pts": np.linspace(0, 30, 120) + 1.0,
    })

    model = train_ridge("QB", frame)
    prediction = model.predict(np.array([[10.0, 10.0, 10.0, 10.0]]))

    assert abs(prediction[0] - 11.0) < 0.5


def test_blend_weight_is_one_when_own_is_perfect():
    frame = pl.DataFrame({
        "pos": ["QB"] * 120,
        "proj_pts": np.zeros(120),
        "ewma": np.linspace(0, 30, 120),
        "act_pts": np.linspace(0, 30, 120),
    })

    assert blend_weight(frame, "QB") == 1.0


def test_walk_forward_never_uses_future_weeks():
    frame = pl.DataFrame({
        "season": [2023] * 4, "week": [1, 1, 2, 2], "sleeper_id": ["a", "b", "a", "b"],
        "pos": ["QB", "QB", "QB", "QB"], "team": ["TB"] * 4,
        "act_pts": [10.0, 12.0, 30.0, 8.0], "proj_pts": [15.0, 14.0, 16.0, 15.0],
        "played": [True] * 4,
    })

    predictions = walk_forward(frame)
    week2 = predictions.filter(pl.col("week") == 2).sort("sleeper_id")

    features = build_features(frame).filter(pl.col("week") == 2).sort("sleeper_id")
    assert week2.get_column("own").to_list() == features.get_column("ewma").to_list()
    assert all(weight == 0.0 for weight in week2.get_column("blend_weight").to_list())
