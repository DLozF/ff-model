import numpy as np
import polars as pl

from ffm.league import partial_synthetic_league, synthetic_draft


def test_synthetic_draft_builds_unique_legal_rosters():
    positions = np.array((["QB"] * 30 + ["RB"] * 80 + ["WR"] * 90 + ["TE"] * 40 + ["K"] * 25 + ["DEF"] * 25))
    players = pl.DataFrame({
        "sleeper_id": [str(i) for i in range(positions.size)],
        "name": [f"P{i}" for i in range(positions.size)],
        "pos": positions,
        "ros_points": np.linspace(300, 1, positions.size),
        "market_value": np.linspace(300, 1, positions.size),
    })

    league = synthetic_draft(players, teams=12, roster_size=15)
    drafted = [player for roster in league["rosters"] for player in roster]

    assert len(drafted) == 180
    assert len(set(drafted)) == 180
    for roster in league["rosters"]:
        roster_pos = positions[np.array(roster)]
        assert np.sum(roster_pos == "QB") >= 1
        assert np.sum(roster_pos == "RB") >= 2
        assert np.sum(roster_pos == "WR") >= 2
        assert np.sum(roster_pos == "TE") >= 1
        assert np.sum(roster_pos == "K") == 1
        assert np.sum(roster_pos == "DEF") == 1


def test_synthetic_draft_orders_players_by_market_value():
    players = pl.DataFrame({
        "sleeper_id": ["rb", "wr", "qb", "te", "k", "def"],
        "name": ["RB", "WR", "QB", "TE", "K", "DEF"],
        "pos": ["RB", "WR", "QB", "TE", "K", "DEF"],
        "ros_points": [1.0, 999.0, 500.0, 400.0, 300.0, 200.0],
        "market_value": [1000.0, 1.0, 500.0, 400.0, 300.0, 200.0],
    })

    league = synthetic_draft(players, teams=1, roster_size=1)

    assert league["rosters"] == [[0]]


def test_partial_synthetic_league_keeps_real_roster_and_avoids_duplicates():
    positions = np.array((["QB"] * 30 + ["RB"] * 80 + ["WR"] * 90 + ["TE"] * 40 + ["K"] * 25 + ["DEF"] * 25))
    players = pl.DataFrame({
        "sleeper_id": [f"p{i}" for i in range(len(positions))],
        "name": [f"Player {i}" for i in range(len(positions))],
        "pos": positions,
        "market_value": np.arange(len(positions), dtype=float),
    })
    real_ids = ["p0", "p30", "p110", "p200", "p240", "p265"]

    league = partial_synthetic_league(players, real_ids, "Real Team", teams=12, roster_size=15)
    drafted = [player for roster in league["rosters"] for player in roster]

    assert league["teams"][0] == "Real Team"
    assert league["rosters"][0] == [0, 30, 110, 200, 240, 265]
    assert len(drafted) == len(set(drafted))
    assert not set(league["rosters"][0]) & set(player for roster in league["rosters"][1:] for player in roster)
