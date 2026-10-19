import polars as pl

from ffm.league import load_real_league


def test_load_real_league_maps_sleeper_ids_to_player_indices(tmp_path):
    pl.DataFrame({"team_id": [1, 2], "team_name": ["A", "B"]}).write_parquet(tmp_path / "yahoo_teams.parquet")
    pl.DataFrame({"team_id": [1, 2], "sleeper_id": ["s1", "s2"]}).write_parquet(tmp_path / "yahoo_rosters.parquet")
    pl.DataFrame({"sleeper_id": ["s3"]}).write_parquet(tmp_path / "yahoo_free_agents.parquet")
    pl.DataFrame({"team_id": [1, 2], "wins": [3, 2]}).write_parquet(tmp_path / "yahoo_standings.parquet")
    players = pl.DataFrame({"sleeper_id": ["s1", "s2", "s3"], "player_index": [10, 11, 12]})

    league = load_real_league(tmp_path, players)

    assert league["teams"] == ["A", "B"]
    assert league["rosters"] == [[10], [11]]
    assert league["free_agents"] == [12]
    assert league["standings"][0]["wins"] == 3
