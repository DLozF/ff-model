import polars as pl

from ffm.config import load_config
from ffm.dataset import build_player_weeks


def test_build_player_weeks_joins_and_filters():
    projections = pl.DataFrame({
        "season": [2025, 2025], "week": [1, 1], "player_id": ["1", "2"],
        "name": ["One", "Two"], "position": ["WR", "RB"],
        "team": ["LA", "SEA"], "opponent": ["SF", "ARI"],
        "pts_ppr": [10.0, 0.1],
    })
    stats = pl.DataFrame({
        "season": [2025], "week": [1], "player_id": ["1"],
        "rec": [5.0], "rec_yd": [50.0], "rec_td": [1.0], "pts_ppr": [16.0],
    })
    players = pl.DataFrame({
        "player_id": ["1", "2"], "gsis_id": ["g1", "g2"],
        "full_name": ["One", "Two"], "position": ["WR", "RB"], "team": ["LAR", "SEA"],
    })
    result = build_player_weeks(
        projections, stats, players, pl.DataFrame(), pl.DataFrame(), load_config()["scoring"]
    )

    assert result.height == 1
    assert result.row(0, named=True) == {
        "season": 2025, "week": 1, "sleeper_id": "1", "gsis_id": "g1",
        "name": "One", "pos": "WR", "team": "LAR", "opp": "SF",
        "proj_pts": 10.0, "act_pts": 16.0, "played": True,
    }


def test_zero_stat_placeholder_is_not_marked_played():
    projections = pl.DataFrame({
        "season": [2025], "week": [1], "player_id": ["2"], "name": ["Two"],
        "position": ["RB"], "team": ["SEA"], "opponent": ["ARI"], "pts_ppr": [5.0],
    })
    stats = pl.DataFrame({
        "season": [2025], "week": [1], "player_id": ["2"], "pts_ppr": [0.0], "gp": [0.0],
    })
    players = pl.DataFrame({
        "player_id": ["2"], "gsis_id": ["g2"], "full_name": ["Two"],
        "position": ["RB"], "team": ["SEA"],
    })

    result = build_player_weeks(
        projections, stats, players, pl.DataFrame(), pl.DataFrame(), load_config()["scoring"]
    )

    assert result.get_column("played").to_list() == [False]


def test_snap_without_actual_stats_is_not_marked_played():
    projections = pl.DataFrame({
        "season": [2026], "week": [6], "player_id": ["2"], "name": ["Two"],
        "position": ["RB"], "team": ["SEA"], "opponent": ["ARI"], "pts_ppr": [8.0],
    })
    stats = pl.DataFrame(schema={"season": pl.Int64, "week": pl.Int64, "player_id": pl.String})
    players = pl.DataFrame({
        "player_id": ["2"], "gsis_id": ["g2"], "full_name": ["Two"],
        "position": ["RB"], "team": ["SEA"],
    })
    ids = pl.DataFrame({"pfr_id": ["p2"], "sleeper_id": ["2"]})
    snaps = pl.DataFrame({
        "season": [2026], "week": [6], "pfr_player_id": ["p2"],
        "offense_snaps": [20.0], "defense_snaps": [0.0], "st_snaps": [0.0],
    })

    result = build_player_weeks(
        projections, stats, players, ids, snaps, load_config()["scoring"]
    )

    assert result.get_column("played").to_list() == [False]
