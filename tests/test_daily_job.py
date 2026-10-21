import json

import polars as pl

from scripts.daily_job import current_opponent, injury_diff, status_play_probability


def test_injury_diff_only_returns_changed_players():
    previous = pl.DataFrame({
        "player_id": ["1", "2"],
        "full_name": ["A", "B"],
        "team": ["SEA", "DEN"],
        "position": ["RB", "WR"],
        "injury_status": [None, "Questionable"],
        "status": ["Active", "Active"],
        "active": [True, True],
    })
    current = previous.with_columns(
        pl.when(pl.col("player_id") == "2")
        .then(pl.lit("Out"))
        .otherwise(pl.col("injury_status"))
        .alias("injury_status")
    )

    changes = injury_diff(current, previous)

    assert changes.get_column("player_id").to_list() == ["2"]
    assert changes.get_column("previous_injury_status").item() == "Questionable"


def test_status_probability_uses_p4_values_and_override_wins():
    availability = {
        "status_play_probability": {
            "none": {"probability": 0.98},
            "Questionable": {"probability": 0.65},
            "Out": {"probability": 0.01},
        }
    }

    assert status_play_probability("Questionable", "Active", availability) == 0.65
    assert status_play_probability(None, "Active", availability) == 0.98
    assert status_play_probability("Questionable", "Active", availability, True) == 0.0
    assert status_play_probability("IR", "Injured Reserve", availability) == 0.0


def test_current_opponent_uses_same_round_robin_as_season_simulation():
    league = {"teams": [f"Team {index}" for index in range(12)]}

    opponent = current_opponent(league, 0)

    assert opponent == 11
