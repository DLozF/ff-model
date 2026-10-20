from ffm.config import load_config
from ffm.scoring import fantasy_points, nflverse_stat_line


SCORING = load_config()["scoring"]


def test_scores_standard_offense():
    stats = {"pass_yd": 250, "pass_td": 2, "pass_int": 1, "rush_yd": 20}
    assert fantasy_points(stats, "QB", SCORING) == 19


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
