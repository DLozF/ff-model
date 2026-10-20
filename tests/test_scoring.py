import polars as pl

from ffm.config import load_config
from ffm.scoring import fantasy_points, nflverse_stat_line, score_projection_frame


SCORING = load_config()["scoring"]


def test_scores_configured_offense():
    stats = {"pass_yd": 250, "pass_td": 2, "pass_int": 1, "rush_yd": 20}
    assert fantasy_points(stats, "QB", SCORING) == 22


def test_scores_kicker_distance_buckets():
    stats = {"xpm": 2, "fgm_20_29": 1, "fgm_40_49": 1, "fgm_50_59": 1}
    assert fantasy_points(stats, "K", SCORING) == 14


def test_scores_defense_points_allowed_tier():
    stats = {"sack": 3, "int": 1, "fum_rec": 1, "def_td": 1, "pts_allow": 10}
    assert fantasy_points(stats, "DEF", SCORING) == 17


def test_nflverse_stat_line_maps_player_fields():
    row = {
        "passing_yards": 250, "passing_tds": 2, "passing_interceptions": 1,
        "passing_2pt_conversions": 1, "rushing_yards": 20, "rushing_tds": 1,
        "rushing_2pt_conversions": 0, "receptions": 3, "receiving_yards": 40,
        "receiving_tds": 1, "receiving_2pt_conversions": 0,
        "fumbles_lost_total": 1, "special_teams_tds": 1, "pat_made": 2,
        "fg_made_0_19": 0, "fg_made_20_29": 1, "fg_made_30_39": 1,
        "fg_made_40_49": 1, "fg_made_50_59": 1, "fg_made_60_": 1,
    }

    mapped = nflverse_stat_line(row)

    assert mapped["pass_yd"] == 250
    assert mapped["fum_lost"] == 1
    assert mapped["ret_td"] == 1
    assert mapped["xpm"] == 2
    assert mapped["fgm_60p"] == 1


def test_scores_yahoo_passing_bonuses_by_hand():
    stats = {
        "pass_yd": 320, "pass_td": 3, "pass_int": 0,
        "pass_cmp_40p": 1, "pass_td_40p": 1,
    }

    assert fantasy_points(stats, "QB", SCORING) == 35.8


def test_scores_yahoo_rushing_bonuses_by_hand():
    stats = {"rush_yd": 110, "rush_40p": 1}

    assert fantasy_points(stats, "RB", SCORING) == 14.0


def test_milestone_scoring_supports_highest_and_stacked_modes():
    stats = {"rush_yd": 160}
    highest = {**SCORING, "milestone_mode": "highest"}
    stacked = {**SCORING, "milestone_mode": "stacked"}

    assert fantasy_points(stats, "RB", highest) == 19.0
    assert fantasy_points(stats, "RB", stacked) == 22.0


def test_score_projection_frame_uses_stat_lines_without_unprojectable_bonuses():
    frame = pl.DataFrame({
        "position": ["QB"], "pts_ppr": [99.0], "pass_yd": [320.0],
        "pass_td": [3.0], "pass_int": [1.0],
    })

    scored = score_projection_frame(frame, SCORING)

    assert scored.item(0, "proj_pts") == 28.8
