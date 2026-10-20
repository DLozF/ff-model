import polars as pl

from ffm.pbp_bonus import PBP_COLUMNS, aggregate_bonus_stats, select_bonus_pbp


def test_select_bonus_pbp_keeps_available_columns_once():
    frame = pl.DataFrame({"season": [2025], "week": [1], "desc": ["play"], "unused": [1]})

    selected = select_bonus_pbp(frame)

    assert selected.columns == [column for column in PBP_COLUMNS if column in frame.columns]


def test_aggregate_bonus_stats_counts_long_plays_and_fourth_down_stops():
    pbp = pl.DataFrame({
        "season": [2025, 2025, 2025, 2025], "week": [1, 1, 1, 1],
        "posteam": ["A", "A", "A", "A"], "defteam": ["B", "B", "B", "B"],
        "down": [1.0, 1.0, 1.0, 4.0], "fourth_down_failed": [0.0, 0.0, 0.0, 1.0],
        "punt_attempt": [0.0, 0.0, 0.0, 0.0], "field_goal_attempt": [0.0, 0.0, 0.0, 0.0],
        "complete_pass": [1.0, 0.0, 0.0, 0.0], "pass_touchdown": [1.0, 0.0, 0.0, 0.0],
        "passing_yards": [45.0, 0.0, 0.0, 0.0], "receiving_yards": [45.0, 0.0, 0.0, 0.0],
        "rushing_yards": [0.0, 42.0, 0.0, 0.0], "rush_touchdown": [0.0, 1.0, 0.0, 0.0],
        "passer_player_id": ["g1", None, None, None], "receiver_player_id": ["g2", None, None, None],
        "rusher_player_id": [None, "g3", None, None], "extra_point_attempt": [0.0, 0.0, 1.0, 0.0],
        "touchdown": [1.0, 1.0, 1.0, 0.0], "td_team": ["A", "A", "B", None],
        "return_touchdown": [0.0, 0.0, 0.0, 0.0],
    })
    ids = pl.DataFrame({"gsis_id": ["g1", "g2", "g3"], "sleeper_id": ["s1", "s2", "s3"]})

    result = aggregate_bonus_stats(pbp, ids)

    assert result.filter(pl.col("player_id") == "s1").item(0, "pass_td_40p") == 1
    assert result.filter(pl.col("player_id") == "s2").item(0, "rec_td_40p") == 1
    assert result.filter(pl.col("player_id") == "s3").item(0, "rush_td_40p") == 1
    defense = result.filter(pl.col("player_id") == "B").row(0, named=True)
    assert defense["fourth_down_stop"] == 1
    assert defense["xp_return"] == 1
