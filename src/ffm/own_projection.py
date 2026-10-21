"""Pregame feature construction and ridge projections for the Task 02 backtest."""
import numpy as np
import polars as pl


TRAINING_START = 2021


def ewma(values: np.ndarray, half_life: float) -> float:
    """Return the exponentially weighted mean of past values in chronological order."""
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return 0.0
    weights = 0.5 ** (np.arange(values.size)[::-1] / half_life)
    return float(np.dot(weights, values) / weights.sum())


def fit_half_life(frame: pl.DataFrame) -> dict[str, float]:
    """Fit per-position EWMA half-life on training data by grid search."""
    half_lives = {}
    for position in sorted(frame.get_column("pos").unique().to_list()):
        rows = frame.filter(pl.col("pos") == position).sort("season", "week")
        actual = rows.get_column("act_pts").to_numpy()
        best = (None, float("inf"))
        for half_life in (1.0, 2.0, 3.0, 4.0, 6.0, 8.0):
            prediction = np.full(actual.size, np.nan)
            for index in range(1, actual.size):
                window = actual[max(0, index - 8):index]
                if window.size:
                    prediction[index] = ewma(window, half_life)
            valid = np.isfinite(prediction)
            mae = float(np.mean(np.abs(actual[valid] - prediction[valid])))
            if mae < best[1]:
                best = (half_life, mae)
        half_lives[position] = best[0] or 3.0
    return half_lives


def build_features(frame: pl.DataFrame, half_lives: dict[str, float] | None = None) -> pl.DataFrame:
    """Build EWMA, last-3, and season-average features using only prior games."""
    frame = frame.filter(pl.col("played")).sort("season", "week")
    if half_lives is None:
        half_lives = fit_half_life(frame.filter(pl.col("season") < 2023))
    rows = []
    for group in frame.partition_by("sleeper_id", as_dict=False):
        points = group.get_column("act_pts").to_numpy()
        positions = group.get_column("pos").to_list()
        for index, row in enumerate(group.iter_rows(named=True)):
            history = points[:index]
            rows.append({
                "season": row["season"], "week": row["week"], "sleeper_id": row["sleeper_id"],
                "pos": row["pos"], "team": row["team"], "proj_pts": row["proj_pts"],
                "act_pts": row["act_pts"],
                "last3": float(np.mean(history[-3:])) if history.size else 0.0,
                "season_avg": float(np.mean(history)) if history.size else 0.0,
                "ewma": ewma(history, half_lives.get(row["pos"], 3.0)),
            })
    return pl.DataFrame(rows)
