import csv

from scripts.log_trade import append_trade


def test_append_trade_creates_header_and_preserves_fields(tmp_path):
    path = tmp_path / "trade_log.csv"
    append_trade(path, {
        "date": "2026-10-20",
        "my_team_gives": "AJ Barner",
        "my_team_gets": "Christian McCaffrey",
        "partner": "Team 5",
        "r": "0.000250",
        "model_verdict": "ACCEPT",
        "outcome": "pending",
    })

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows == [{
        "date": "2026-10-20",
        "my_team_gives": "AJ Barner",
        "my_team_gets": "Christian McCaffrey",
        "partner": "Team 5",
        "r": "0.000250",
        "model_verdict": "ACCEPT",
        "outcome": "pending",
    }]
