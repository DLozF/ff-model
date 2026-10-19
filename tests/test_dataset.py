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
