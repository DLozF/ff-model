from ffm.sleeper import projection_records, stat_records


def test_projection_records_flattens_player_and_stats():
    payload = [{
        "player_id": "1", "season": "2025", "week": 5, "team": "LA",
        "opponent": "SF", "category": "proj",
        "player": {"full_name": "Test WR", "position": "WR"},
        "stats": {"pts_ppr": 12.5, "rec": 5},
    }]
    assert projection_records(payload) == [{
        "player_id": "1", "season": 2025, "week": 5, "team": "LAR",
        "opponent": "SF", "name": "Test WR", "position": "WR",
        "pts_ppr": 12.5, "rec": 5,
    }]


def test_stat_records_adds_player_id():
    assert stat_records({"7": {"pts_ppr": 8.0, "gp": 1}}) == [
        {"player_id": "7", "pts_ppr": 8.0, "gp": 1}
    ]
