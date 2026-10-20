from collections import defaultdict

import polars as pl

from ffm.ids import normalize_team

PBP_COLUMNS = (
    "season", "week", "game_id", "posteam", "defteam", "play_type", "down",
    "fourth_down_converted", "fourth_down_failed", "punt_attempt",
    "field_goal_attempt", "complete_pass", "pass_touchdown", "passing_yards",
    "passer_player_id", "rusher_player_id", "receiver_player_id",
    "rush_touchdown", "receiving_yards", "rushing_yards", "return_touchdown",
    "kickoff_attempt", "extra_point_attempt", "two_point_attempt", "td_team",
    "touchdown", "desc",
)


def select_bonus_pbp(frame: pl.DataFrame) -> pl.DataFrame:
    """Keep only fields required to derive custom Yahoo bonus statistics."""
    return frame.select([column for column in PBP_COLUMNS if column in frame.columns])


BONUS_COLUMNS = (
    "pass_cmp_40p", "pass_td_40p", "rush_40p", "rush_td_40p",
    "rec_40p", "rec_td_40p", "fourth_down_stop", "xp_return", "def_kr_pr_td",
)


def aggregate_bonus_stats(pbp: pl.DataFrame, ids: pl.DataFrame) -> pl.DataFrame:
    """Aggregate Yahoo long-play and defense bonuses from nflverse play-by-play."""
    mapping = {
        str(row["gsis_id"]): str(row["sleeper_id"])
        for row in ids.select("gsis_id", "sleeper_id").drop_nulls().iter_rows(named=True)
    }
    totals = defaultdict(lambda: defaultdict(float))

    def add(row, player_key, statistic):
        player = row.get(player_key)
        sleeper = mapping.get(str(player)) if player is not None else None
        if sleeper:
            totals[(int(row["season"]), int(row["week"]), sleeper)][statistic] += 1.0

    for row in pbp.iter_rows(named=True):
        passing_yards = float(row.get("passing_yards") or 0)
        receiving_yards = float(row.get("receiving_yards") or 0)
        rushing_yards = float(row.get("rushing_yards") or 0)
        if row.get("complete_pass") == 1 and passing_yards >= 40:
            add(row, "passer_player_id", "pass_cmp_40p")
            add(row, "receiver_player_id", "rec_40p")
        if row.get("pass_touchdown") == 1 and passing_yards >= 40:
            add(row, "passer_player_id", "pass_td_40p")
            add(row, "receiver_player_id", "rec_td_40p")
        if rushing_yards >= 40:
            add(row, "rusher_player_id", "rush_40p")
            if row.get("rush_touchdown") == 1:
                add(row, "rusher_player_id", "rush_td_40p")
        defense = normalize_team(row.get("defteam"))
        key = (int(row["season"]), int(row["week"]), defense) if defense else None
        if key and row.get("down") == 4 and row.get("fourth_down_failed") == 1:
            if row.get("punt_attempt") != 1 and row.get("field_goal_attempt") != 1:
                totals[key]["fourth_down_stop"] += 1.0
        if key and row.get("extra_point_attempt") == 1 and row.get("touchdown") == 1:
            if normalize_team(row.get("td_team")) == defense:
                totals[key]["xp_return"] += 1.0
        if row.get("return_touchdown") == 1 and (
            row.get("kickoff_attempt") == 1 or row.get("punt_attempt") == 1
        ):
            team = normalize_team(row.get("td_team"))
            if team:
                totals[(int(row["season"]), int(row["week"]), team)]["def_kr_pr_td"] += 1.0
    records = []
    for (season, week, player_id), values in totals.items():
        records.append({
            "season": season, "week": week, "player_id": player_id,
            **{column: values[column] for column in BONUS_COLUMNS},
        })
    schema = {
        "season": pl.Int64, "week": pl.Int64, "player_id": pl.String,
        **{column: pl.Float64 for column in BONUS_COLUMNS},
    }
    return pl.from_dicts(records, schema=schema).sort("season", "week", "player_id")


def merge_bonus_stats(stats: pl.DataFrame, bonus: pl.DataFrame) -> pl.DataFrame:
    """Replace source bonus columns with play-by-play counts when available."""
    existing = [column for column in BONUS_COLUMNS if column in stats.columns]
    base = stats.drop(existing)
    return base.join(bonus, on=["season", "week", "player_id"], how="left").with_columns(
        pl.col(column).fill_null(0.0) for column in BONUS_COLUMNS
    )
