"""Past-only expected Yahoo bonus projections."""
from __future__ import annotations

import numpy as np
import polars as pl

YARD_SPECS = {
    "pass": ("proj_pass_yd", "actual_pass_yd", "proj_pass_td", "actual_pass_td",
             "pass_cmp_40p", "pass_td_40p", "pass_yd_milestones"),
    "rush": ("proj_rush_yd", "actual_rush_yd", "proj_rush_td", "actual_rush_td",
             "rush_40p", "rush_td_40p", "rush_yd_milestones"),
    "rec": ("proj_rec_yd", "actual_rec_yd", "proj_rec_td", "actual_rec_td",
            "rec_40p", "rec_td_40p", "rec_yd_milestones"),
}


def week_key(season: int, week: int) -> int:
    return int(season) * 100 + int(week)


def prior_rows(frame: pl.DataFrame, season: int, week: int) -> pl.DataFrame:
    """Return only rows strictly before the target week."""
    key = week_key(season, week)
    return frame.filter(pl.col("season") * 100 + pl.col("week") < key)


def _nearest_indices(projected: float, history_projection, k: int) -> np.ndarray:
    values = np.asarray(history_projection, dtype=float)
    valid = np.isfinite(values)
    indices = np.flatnonzero(valid)
    if indices.size == 0:
        return indices
    count = min(int(k), indices.size)
    distances = np.abs(values[indices] - float(projected))
    return indices[np.argpartition(distances, count - 1)[:count]]


def _milestone_payout(yards: np.ndarray, milestones: list[dict], mode: str) -> np.ndarray:
    if not milestones:
        return np.zeros_like(yards, dtype=float)
    reached = np.stack([
        np.where(yards >= float(row["threshold"]), float(row["points"]), 0.0)
        for row in milestones
    ], axis=1)
    return reached.sum(axis=1) if mode == "stacked" else reached.max(axis=1)


def expected_milestone_bonus(
    projected_yards: float,
    history_projection,
    history_actual,
    milestones: list[dict],
    mode: str = "highest",
    k: int = 300,
) -> float:
    """Estimate expected milestone payout from nearest projected-yard residuals."""
    projection = np.asarray(history_projection, dtype=float)
    actual = np.asarray(history_actual, dtype=float)
    valid = np.isfinite(projection) & np.isfinite(actual)
    projection = projection[valid]
    actual = actual[valid]
    nearest = _nearest_indices(projected_yards, projection, k)
    if nearest.size == 0:
        return 0.0
    simulated = np.maximum(0.0, float(projected_yards) + actual[nearest] - projection[nearest])
    return float(_milestone_payout(simulated, milestones, mode).mean())


def expected_long_play_bonus(
    projected_yards: float,
    projected_tds: float,
    history_projection,
    history_actual,
    history_long,
    history_tds,
    history_long_tds,
    long_points: float,
    long_td_points: float,
    k: int = 300,
    prior_yards: float = 5000.0,
    prior_tds: float = 20.0,
) -> float:
    """Estimate 40+ play and long-TD bonuses with position-level shrinkage."""
    projection = np.asarray(history_projection, dtype=float)
    actual = np.asarray(history_actual, dtype=float)
    long_count = np.asarray(history_long, dtype=float)
    touchdowns = np.asarray(history_tds, dtype=float)
    long_tds = np.asarray(history_long_tds, dtype=float)
    valid = np.isfinite(projection) & np.isfinite(actual)
    if not np.any(valid):
        return 0.0
    projection = projection[valid]
    actual = np.maximum(actual[valid], 0.0)
    long_count = np.nan_to_num(long_count[valid])
    touchdowns = np.nan_to_num(touchdowns[valid])
    long_tds = np.nan_to_num(long_tds[valid])
    global_rate = float(long_count.sum() / max(actual.sum(), 1.0))
    global_td_share = float(long_tds.sum() / max(touchdowns.sum(), 1.0))
    nearest = _nearest_indices(projected_yards, projection, k)
    local_yards = float(actual[nearest].sum())
    rate = float(
        (long_count[nearest].sum() + prior_yards * global_rate)
        / (local_yards + prior_yards)
    )
    local_tds = float(touchdowns[nearest].sum())
    td_share = float(
        (long_tds[nearest].sum() + prior_tds * global_td_share)
        / (local_tds + prior_tds)
    )
    return (
        max(float(projected_yards), 0.0) * rate * float(long_points)
        + max(float(projected_tds), 0.0) * td_share * float(long_td_points)
    )


def _offensive_bonus_arrays(row: dict, arrays: dict[str, np.ndarray], scoring: dict, mode: str) -> float:
    if not arrays:
        return 0.0
    total = 0.0
    for prefix, spec in YARD_SPECS.items():
        proj_yards, actual_yards, proj_tds, actual_tds, long_key, long_td_key, milestone_key = spec
        projected = float(row.get(proj_yards) or 0.0)
        projected_td = float(row.get(proj_tds) or 0.0)
        if projected <= 0 and projected_td <= 0:
            continue
        total += expected_milestone_bonus(
            projected,
            arrays[proj_yards], arrays[actual_yards],
            scoring.get(milestone_key, []),
            mode=mode,
        )
        total += expected_long_play_bonus(
            projected,
            projected_td,
            arrays[proj_yards], arrays[actual_yards], arrays[long_key],
            arrays[actual_tds], arrays[long_td_key],
            scoring.get(long_key, 0.0),
            scoring.get(long_td_key, 0.0),
        )
    return float(total)


def offensive_bonus(row: dict, history: pl.DataFrame, scoring: dict, mode: str) -> float:
    """Return milestone and long-play expectation for one offensive player-week."""
    arrays = {
        column: history.get_column(column).to_numpy()
        for spec in YARD_SPECS.values() for column in spec[:6]
    } if not history.is_empty() else {}
    return _offensive_bonus_arrays(row, arrays, scoring, mode)


def defense_bonus(row: dict, defense_history: pl.DataFrame, scoring: dict) -> float:
    """Estimate fourth-down stops from prior opponent attempts and defense success."""
    points = float(scoring.get("def_fourth_down_stop", 0.0))
    if points == 0 or defense_history.is_empty():
        return 0.0
    league_games = max(defense_history.select("season", "week", "offense").unique().height, 1)
    league_attempts = float(defense_history.get_column("attempts").sum())
    league_stops = float(defense_history.get_column("stops").sum())
    attempts_per_game = league_attempts / league_games
    stop_rate = league_stops / max(league_attempts, 1.0)
    opponent = defense_history.filter(pl.col("offense") == row.get("opp"))
    opponent_games = opponent.select("season", "week").unique().height
    opponent_attempts = (
        float(opponent.get_column("attempts").sum()) + 6.0 * attempts_per_game
    ) / (opponent_games + 6.0)
    team = defense_history.filter(pl.col("defense") == row.get("team"))
    team_attempts = float(team.get_column("attempts").sum())
    team_stops = float(team.get_column("stops").sum())
    team_rate = (team_stops + 20.0 * stop_rate) / (team_attempts + 20.0)
    return float(opponent_attempts * team_rate * points)


def walk_forward_bonus(
    frame: pl.DataFrame,
    defense_weeks: pl.DataFrame,
    scoring: dict,
) -> pl.DataFrame:
    """Add highest, stacked, selected, and bonus-adjusted projections past-only."""
    output = []
    ordered = frame.sort("season", "week", "sleeper_id")
    for season, week in ordered.select("season", "week").unique().sort("season", "week").iter_rows():
        target = ordered.filter((pl.col("season") == season) & (pl.col("week") == week))
        history = prior_rows(ordered.filter(pl.col("played")), season, week)
        defense_history = prior_rows(defense_weeks, season, week)
        history_by_position = {
            position: {
                column: rows.get_column(column).to_numpy()
                for spec in YARD_SPECS.values() for column in spec[:6]
            }
            for position in ("QB", "RB", "WR", "TE")
            for rows in [history.filter(pl.col("pos") == position)]
            if not rows.is_empty()
        }
        highest = []
        stacked = []
        for row in target.iter_rows(named=True):
            if row["pos"] == "DEF":
                value = defense_bonus(row, defense_history, scoring)
                highest.append(value)
                stacked.append(value)
            elif row["pos"] in {"QB", "RB", "WR", "TE"}:
                arrays = history_by_position.get(row["pos"], {})
                highest.append(_offensive_bonus_arrays(row, arrays, scoring, "highest"))
                stacked.append(_offensive_bonus_arrays(row, arrays, scoring, "stacked"))
            else:
                highest.append(0.0)
                stacked.append(0.0)
        mode = scoring.get("milestone_mode", "highest")
        selected = stacked if mode == "stacked" else highest
        output.append(target.with_columns(
            pl.col("proj_pts").alias("rescored_proj"),
            pl.Series("expected_bonus_highest", highest),
            pl.Series("expected_bonus_stacked", stacked),
            pl.Series("expected_bonus", selected),
            (pl.col("proj_pts") + pl.Series(selected)).alias("proj_pts_bonus"),
        ))
    return pl.concat(output).sort("season", "week", "sleeper_id")
