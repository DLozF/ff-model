import polars as pl

from scripts.run_synthetic import fixed_idp_schedule, prepare_players


def test_prepare_players_uses_rescored_projection_points():
    history = pl.DataFrame({
        "season": [2026, 2026], "week": [7, 7], "player_id": ["a", "b"],
        "name": ["A", "B"], "position": ["QB", "RB"], "team": ["BUF", "BAL"],
        "opponent": ["MIA", "CLE"], "proj_pts": [25.0, 10.0],
    })
    sleeper = pl.DataFrame({"player_id": ["a", "b"], "injury_status": [None, None]})

    players, matrix = prepare_players(history, [7], sleeper, forced_ids=["b"])

    assert players.get_column("ros_points").to_list() == [25.0, 10.0]
    assert matrix.tolist() == [[25.0, 10.0]]


def test_fixed_idp_schedule_zeros_out_the_players_bye_week():
    games = [[("BAL", "CLE")], [("BUF", "MIA")]]

    assert fixed_idp_schedule(games, "BAL", 7.95) == [7.95, 0.0]
