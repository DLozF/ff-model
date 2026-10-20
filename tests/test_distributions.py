import numpy as np
import polars as pl

from ffm.distributions import (
    QuantileModel,
    apply_bias_scale,
    fit_bias_scale,
    previous_completed_weeks,
)


def test_quantile_model_is_monotone_and_interpolates():
    frame = pl.DataFrame({
        "pos": ["WR"] * 800,
        "proj_pts": np.linspace(1, 20, 800),
        "act_pts": np.linspace(0, 24, 800) + np.sin(np.arange(800)),
        "played": [True] * 800,
    })
    model = QuantileModel.fit(frame, positions=["WR"], k=300, smooth=5)

    table = model.tables["WR"]
    assert np.all(np.diff(table.quantiles, axis=1) >= -1e-12)
    values = model.ppf("WR", np.array([5.1, 10.2, 25.0]), np.array([0.1, 0.5, 0.9]))
    assert values.shape == (3,)
    assert np.all(np.isfinite(values))
    assert values[2] > values[1]


def test_model_round_trip_npz(tmp_path):
    frame = pl.DataFrame({
        "pos": ["QB"] * 400,
        "proj_pts": np.tile(np.arange(20), 20),
        "act_pts": np.tile(np.arange(20), 20) + 1,
        "played": [True] * 400,
    })
    model = QuantileModel.fit(frame, positions=["QB"], k=300, smooth=5)
    path = tmp_path / "quantiles.npz"
    model.save(path)

    loaded = QuantileModel.load(path)

    assert np.array_equal(loaded.levels, model.levels)
    assert np.allclose(loaded.tables["QB"].quantiles, model.tables["QB"].quantiles)


def test_apply_bias_scale_preserves_floor_and_monotonicity():
    base = np.array([[2.0, 5.0, 8.0]])

    adjusted = apply_bias_scale(
        projection=np.array([5.0]), quantiles=base, bias=-4.0, scale=2.0, floor=0.0
    )

    assert np.allclose(adjusted, [[0.0, 1.0, 7.0]])
    assert np.all(np.diff(adjusted, axis=1) >= 0)


def test_fit_bias_scale_shrinks_toward_identity():
    projection = np.full(400, 10.0)
    base = np.tile(np.array([8.0, 10.0, 12.0]), (400, 1))
    actual = np.tile(np.array([8.0, 12.0, 16.0, 12.0]), 100)
    levels = np.array([0.25, 0.50, 0.75])

    result = fit_bias_scale(projection, actual, base, levels, floor=0.0, prior_weight=200)

    assert result["n"] == 400
    assert result["weight"] == 400 / 600
    assert result["bias"] != result["raw_bias"]
    assert abs(result["bias"]) < abs(result["raw_bias"])
    assert abs(result["scale"] - 1) < abs(result["raw_scale"] - 1)


def test_previous_completed_weeks_crosses_seasons_without_leakage():
    frame = pl.DataFrame({
        "season": [2025, 2025, 2025, 2026, 2026],
        "week": [16, 17, 18, 1, 2],
    })

    weeks = previous_completed_weeks(frame, season=2026, week=2, window=3)

    assert weeks == [(2025, 17), (2025, 18), (2026, 1)]
