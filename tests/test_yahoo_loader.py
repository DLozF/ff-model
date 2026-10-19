import json
from pathlib import Path

import polars as pl

from ffm.yahoo_loader import parse_yahoo_payload


def test_fake_yahoo_json_produces_rosters_and_settings():
    payload = json.loads((Path(__file__).parent / "fixtures/yahoo_fake.json").read_text())
    ids = pl.DataFrame({
        "yahoo_id": [101, 103, 104],
        "sleeper_id": ["s101", "s103", "s104"],
    })

    tables = parse_yahoo_payload(payload, ids)

    assert tables["settings"]["teams"] == 2
    assert tables["settings"]["current_week"] == 6
    assert tables["settings"]["lineup"]["QB"] == 1
    assert tables["settings"]["lineup"]["FLEX"] == 1
    assert tables["settings"]["bench"] == 4
    assert tables["settings"]["scoring"]["pass_yd"] == 0.04
    assert tables["rosters"].filter(pl.col("team_id") == 1).get_column("sleeper_id").to_list() == ["s101", "SEA"]
    assert tables["rosters"].filter(pl.col("team_id") == 2).get_column("team").to_list() == ["LAR"]
    assert tables["standings"].filter(pl.col("team_id") == 1).item(0, "wins") == 4
