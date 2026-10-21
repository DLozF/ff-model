import json

import polars as pl

from scripts.explain_week import main as explain_main
import subprocess
import sys


def test_projection_scorecard_decision_is_reproducible():
    import numpy as np

    from ffm.backtest_projection import blend_weight, train_ridge

    frame = pl.DataFrame({
        "pos": ["QB"] * 60,
        "proj_pts": np.linspace(0, 20, 60),
        "last3": np.linspace(0, 20, 60),
        "season_avg": np.linspace(0, 20, 60),
        "ewma": np.linspace(0, 20, 60),
        "act_pts": np.linspace(0, 20, 60) + 0.5,
    })
    first = train_ridge("QB", frame)
    second = train_ridge("QB", frame)

    assert abs(first.predict(np.array([[5.0, 5.0, 5.0, 5.0]]))[0] - second.predict(np.array([[5.0, 5.0, 5.0, 5.0]]))[0]) < 1e-9
    assert blend_weight(frame, "QB") == blend_weight(frame, "QB")
