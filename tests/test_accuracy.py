import polars as pl

from ffm.accuracy import add_vegas_feature, implied_team_points, role_change_features


def test_implied_team_points_uses_spread_and_week_mean():
    schedules = pl.DataFrame({
        "season": [2025, 2025], "week": [1, 1], "game_type": ["REG", "REG"],
        "home_team": ["A", "C"], "away_team": ["B", "D"],
        "total_line": [50.0, 40.0], "spread_line": [4.0, -2.0],
    })

    result = implied_team_points(schedules).sort("team")

    assert result.get_column("implied_points").to_list() == [27.0, 23.0, 19.0, 21.0]
    assert result.get_column("implied_delta").to_list() == [4.5, 0.5, -3.5, -1.5]


def test_defense_uses_opponent_implied_points():
    frame = pl.DataFrame({
        "season": [2025, 2025], "week": [1, 1], "pos": ["WR", "DEF"],
        "team": ["A", "A"], "opp": ["B", "B"],
    })
    implied = pl.DataFrame({
        "season": [2025, 2025], "week": [1, 1], "team": ["A", "B"],
        "implied_points": [27.0, 23.0], "implied_delta": [2.0, -2.0],
    })

    result = add_vegas_feature(frame, implied)

    assert result.get_column("vegas_delta").to_list() == [2.0, -2.0]


def test_role_change_uses_only_prior_six_weeks():
    snaps = pl.DataFrame({
        "season": [2025] * 7,
        "week": list(range(1, 8)),
        "pfr_player_id": ["p1"] * 7,
        "offense_pct": [0.1, 0.2, 0.3, 0.4, 0.7, 0.9, 1.0],
    })
    mapping = pl.DataFrame({"pfr_id": ["p1"], "gsis_id": ["g1"]})

    result = role_change_features(snaps, mapping).filter(pl.col("week") == 7)

    assert result.item(0, "gsis_id") == "g1"
    assert result.item(0, "role_delta") == 0.55
