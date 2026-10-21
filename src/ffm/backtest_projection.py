"""Walk-forward ridge projection and Task 02 scorecard assembly."""
import numpy as np
import polars as pl
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ffm.own_projection import build_features, fit_half_life

FEATURES = ("proj_pts", "last3", "season_avg", "ewma")
EXPANDED_FEATURES = FEATURES + (
    "snap_share", "target_share", "carry_share", "team_implied_points", "spread",
    "opponent_pos_allowed", "home", "qb_change",
)
TEST_SEASONS = (2023, 2024, 2025, 2026)


def train_ridge(position: str, history: pl.DataFrame, seed: int = 2026) -> Ridge | None:
    """Fit one ridge model per position on strictly prior played weeks."""
    rows = history.filter(pl.col("pos") == position)
    if rows.height < 50:
        return None
    model = Ridge(alpha=1.0, random_state=seed)
    model.fit(rows.select(FEATURES).to_numpy(), rows.get_column("act_pts").to_numpy())
    return model


def train_expanded_ridge(position: str, history: pl.DataFrame, seed: int = 2026):
    """Fit a standardized ridge model on the complete preregistered feature set."""
    rows = history.filter(pl.col("pos") == position)
    if rows.height < 50:
        return None
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0, random_state=seed))
    model.fit(rows.select(EXPANDED_FEATURES).to_numpy(), rows.get_column("act_pts").to_numpy())
    return model


def walk_forward_expanded(features: pl.DataFrame) -> pl.DataFrame:
    """Predict with expanded ridge models fitted only on prior season-weeks."""
    features = features.sort("season", "week", "sleeper_id")
    outputs = []
    for season in TEST_SEASONS:
        season_rows = features.filter(pl.col("season") == season)
        for week in sorted(season_rows.get_column("week").unique().to_list()):
            prior = features.filter(
                (pl.col("season") < season)
                | ((pl.col("season") == season) & (pl.col("week") < week))
            )
            test = season_rows.filter(pl.col("week") == week)
            predictions = []
            for position in sorted(test.get_column("pos").unique().to_list()):
                rows = test.filter(pl.col("pos") == position)
                model = train_expanded_ridge(position, prior)
                prediction = (
                    model.predict(rows.select(EXPANDED_FEATURES).to_numpy())
                    if model is not None else rows.get_column("proj_pts").to_numpy()
                )
                predictions.append(rows.with_columns(
                    pl.Series("expanded_ridge", np.maximum(prediction, 0.0))
                ))
            outputs.append(pl.concat(predictions))
    return pl.concat(outputs).sort("season", "week", "sleeper_id")


def blend_weight(history: pl.DataFrame, position: str) -> float:
    """Fit the blend weight on past weeks only by minimizing MAE."""
    rows = history.filter(pl.col("pos") == position)
    if rows.height < 50:
        return 0.0
    actual = rows.get_column("act_pts").to_numpy()
    sleeper = rows.get_column("proj_pts").to_numpy()
    grid = np.linspace(0.0, 1.0, 21)
    losses = [
        float(np.mean(np.abs(actual - (weight * rows.get_column("ewma").to_numpy() + (1 - weight) * sleeper))))
        for weight in grid
    ]
    return float(grid[int(np.argmin(losses))])


def walk_forward(frame: pl.DataFrame) -> pl.DataFrame:
    """Predict every played week with models trained only on earlier weeks."""
    features = build_features(frame).sort("season", "week")
    outputs = []
    for season in TEST_SEASONS:
        season_rows = features.filter(pl.col("season") == season)
        for week in sorted(season_rows.get_column("week").unique().to_list()):
            prior = features.filter((pl.col("season") < season) | (pl.col("season") == season) & (pl.col("week") < week))
            test = season_rows.filter(pl.col("week") == week)
            predictions = []
            for position in sorted(test.get_column("pos").unique().to_list()):
                rows = test.filter(pl.col("pos") == position)
                model = train_ridge(position, prior)
                own = (
                    model.predict(rows.select(FEATURES).to_numpy())
                    if model is not None
                    else rows.get_column("ewma").to_numpy()
                )
                weight = blend_weight(prior, position)
                predictions.append(rows.with_columns(
                    own=own,
                    blended=weight * own + (1 - weight) * rows.get_column("proj_pts").to_numpy(),
                    blend_weight=weight,
                ))
            outputs.append(pl.concat(predictions))
    return pl.concat(outputs).sort("season", "week", "sleeper_id")
