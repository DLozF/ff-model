"""Pregame feature construction and ridge projections for the Task 02 backtest."""
import numpy as np
import polars as pl

from ffm.ids import normalize_team


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


def build_features(
    frame: pl.DataFrame,
    half_lives: dict[str, float] | None = None,
    include_unplayed: bool = False,
) -> pl.DataFrame:
    """Build EWMA, last-3, and season-average features using only prior games."""
    frame = frame.sort("season", "week")
    played = frame.filter(pl.col("played"))
    if half_lives is None:
        half_lives = fit_half_life(played.filter(pl.col("season") < 2023))
    rows = []
    for group in frame.partition_by("sleeper_id", as_dict=False):
        history = []
        for row in group.iter_rows(named=True):
            if not row["played"] and not include_unplayed:
                continue
            values = np.asarray(history, dtype=float)
            feature_row = {
                "season": row["season"], "week": row["week"], "sleeper_id": row["sleeper_id"],
                "pos": row["pos"], "team": row["team"], "proj_pts": row["proj_pts"],
                "act_pts": row["act_pts"], "played": row["played"],
                "last3": float(np.mean(values[-3:])) if values.size else 0.0,
                "season_avg": float(np.mean(values)) if values.size else 0.0,
                "ewma": ewma(values, half_lives.get(row["pos"], 3.0)),
            }
            for column in ("gsis_id", "opp", "name"):
                if column in row:
                    feature_row[column] = row[column]
            rows.append(feature_row)
            if row["played"]:
                history.append(float(row["act_pts"]))
    return pl.DataFrame(rows)


def _schedule_context(schedules: pl.DataFrame) -> dict[tuple[int, int, str], tuple[float, float, float]]:
    context = {}
    for row in schedules.filter(pl.col("game_type") == "REG").iter_rows(named=True):
        if row.get("total_line") is None or row.get("spread_line") is None:
            continue
        season, week = int(row["season"]), int(row["week"])
        total, spread = float(row["total_line"]), float(row["spread_line"])
        home, away = normalize_team(row["home_team"]), normalize_team(row["away_team"])
        context[(season, week, home)] = ((total + spread) / 2, spread, 1.0)
        context[(season, week, away)] = ((total - spread) / 2, -spread, 0.0)
    return context


def build_context_features(
    frame: pl.DataFrame,
    stats: pl.DataFrame,
    snaps: pl.DataFrame,
    mapping: pl.DataFrame,
    schedules: pl.DataFrame,
    half_lives: dict[str, float] | None = None,
    include_unplayed: bool = False,
) -> pl.DataFrame:
    """Add strictly pregame role, Vegas, opponent, and QB-continuity features."""
    base = build_features(
        frame, half_lives=half_lives, include_unplayed=include_unplayed
    ).sort("season", "week", "sleeper_id")
    if "season_type" in stats.columns:
        stats = stats.filter(pl.col("season_type") == "REG")
    stats = stats.with_columns(pl.col("team").map_elements(normalize_team, return_dtype=pl.String))
    player_week = {
        (int(row["season"]), int(row["week"]), row["player_id"]): row
        for row in stats.select("season", "week", "player_id", "team", "targets", "carries", "attempts")
        .group_by("season", "week", "player_id", "team")
        .agg(pl.col("targets").sum(), pl.col("carries").sum(), pl.col("attempts").sum())
        .iter_rows(named=True)
    }
    team_totals = {}
    for row in stats.group_by("season", "week", "team").agg(
        pl.col("attempts").sum().alias("pass_attempts"),
        pl.col("carries").sum().alias("rush_attempts"),
    ).iter_rows(named=True):
        team_totals[(int(row["season"]), int(row["week"]), row["team"])] = row
    team_weeks: dict[tuple[int, str], list[int]] = {}
    for season, week, team in team_totals:
        team_weeks.setdefault((season, team), []).append(week)
    for weeks in team_weeks.values():
        weeks.sort()

    snap_rows = (
        snaps.select("season", "week", "pfr_player_id", "offense_pct")
        .join(mapping.select("pfr_id", "gsis_id"), left_on="pfr_player_id", right_on="pfr_id")
        .group_by("season", "week", "gsis_id").agg(pl.col("offense_pct").mean())
    )
    snap_map = {
        (int(row["season"]), int(row["week"]), row["gsis_id"]): float(row["offense_pct"] or 0.0)
        for row in snap_rows.iter_rows(named=True)
    }
    schedule = _schedule_context(schedules)

    actual_qbs: dict[tuple[int, str], list[tuple[int, str]]] = {}
    qb_rows = stats.filter(pl.col("attempts") > 0).sort("attempts", descending=True).unique(
        ["season", "week", "team"], keep="first"
    )
    for row in qb_rows.iter_rows(named=True):
        actual_qbs.setdefault((int(row["season"]), row["team"]), []).append(
            (int(row["week"]), row["player_id"])
        )
    for rows in actual_qbs.values():
        rows.sort()
    projected_qb = {
        (int(row["season"]), int(row["week"]), row["team"]): row.get("gsis_id")
        for row in base.filter(pl.col("pos") == "QB").sort("proj_pts", descending=True)
        .unique(["season", "week", "team"], keep="first").iter_rows(named=True)
    }

    allowed_week = (
        base.filter(pl.col("played")).group_by("season", "week", "opp", "pos")
        .agg(pl.col("act_pts").sum().alias("points"))
    )
    allowed_by_opponent: dict[tuple[int, str, str], list[tuple[int, float]]] = {}
    allowed_by_position: dict[tuple[int, str], list[tuple[int, float]]] = {}
    for value in allowed_week.iter_rows(named=True):
        season, week = int(value["season"]), int(value["week"])
        points = float(value["points"])
        allowed_by_opponent.setdefault((season, value["opp"], value["pos"]), []).append((week, points))
        allowed_by_position.setdefault((season, value["pos"]), []).append((week, points))
    opponent_cache = {}
    results = []
    for row in base.iter_rows(named=True):
        season, week = int(row["season"]), int(row["week"])
        team, opponent, player = row["team"], row.get("opp"), row.get("gsis_id")
        prior_weeks = [value for value in team_weeks.get((season, team), []) if value < week][-4:]
        pass_attempts = sum(float(team_totals[(season, value, team)]["pass_attempts"] or 0.0) for value in prior_weeks)
        rush_attempts = sum(float(team_totals[(season, value, team)]["rush_attempts"] or 0.0) for value in prior_weeks)
        targets = sum(float(player_week.get((season, value, player), {}).get("targets", 0.0) or 0.0) for value in prior_weeks)
        carries = sum(float(player_week.get((season, value, player), {}).get("carries", 0.0) or 0.0) for value in prior_weeks)
        snap_values = [snap_map.get((season, value, player), 0.0) for value in prior_weeks]

        opponent_key = (season, week, opponent, row["pos"])
        if opponent_key not in opponent_cache:
            prior_allowed = [
                points for value_week, points in allowed_by_opponent.get((season, opponent, row["pos"]), [])
                if value_week < week
            ][-8:]
            league_allowed = [
                points for value_week, points in allowed_by_position.get((season, row["pos"]), [])
                if value_week < week
            ]
            league_mean = float(np.mean(league_allowed)) if league_allowed else 0.0
            opponent_cache[opponent_key] = (
                sum(prior_allowed) + 4.0 * league_mean
            ) / (len(prior_allowed) + 4.0)
        opponent_points = opponent_cache[opponent_key]

        current_qb = projected_qb.get((season, week, team))
        previous = [value for value in actual_qbs.get((season, team), []) if value[0] < week]
        previous_qb = previous[-1][1] if previous else None
        implied, spread, home = schedule.get((season, week, team), (0.0, 0.0, 0.0))
        row.update({
            "snap_share": float(np.mean(snap_values)) if snap_values else 0.0,
            "target_share": targets / pass_attempts if pass_attempts > 0 else 0.0,
            "carry_share": carries / rush_attempts if rush_attempts > 0 else 0.0,
            "team_implied_points": implied,
            "spread": spread,
            "home": home,
            "opponent_pos_allowed": opponent_points,
            "qb_change": float(bool(previous_qb and current_qb and previous_qb != current_qb)),
        })
        results.append(row)
    return pl.DataFrame(results)
