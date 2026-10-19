import numpy as np
import polars as pl

from ffm.distributions import QuantileModel


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
