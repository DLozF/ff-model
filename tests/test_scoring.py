from ffm.config import load_config
from ffm.scoring import fantasy_points


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
