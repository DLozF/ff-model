import numpy as np
import polars as pl


def lagged_residual_feature(frame: pl.DataFrame) -> pl.DataFrame:
    """Add a past-only mean residual over the previous three games."""
    return (
        frame.sort("season", "sleeper_id", "week")
        .with_columns((pl.col("act_pts") - pl.col("proj_pts")).alias("residual"))
        .with_columns(
            pl.col("residual")
            .shift(1)
            .rolling_mean(window_size=3, min_samples=1)
            .over("season", "sleeper_id")
            .alias("residual_last3")
        )
    )


def fit_through_origin(feature, target) -> float:
    """Fit a one-variable least-squares coefficient through zero."""
    x = np.asarray(feature, dtype=float)
    y = np.asarray(target, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    denominator = float(x[valid] @ x[valid])
    return float(x[valid] @ y[valid] / denominator) if denominator else 0.0
