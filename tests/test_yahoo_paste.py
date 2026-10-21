from pathlib import Path

import polars as pl

from ffm.yahoo_paste import (
    match_roster, normalize_player_name, parse_available_text, parse_roster_text,
    parse_settings_text,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_settings_extracts_partial_league_rules():
    parsed = parse_settings_text((FIXTURES / "yahoo_settings_fake.txt").read_text())

    assert parsed["league"]["teams"] == 12
    assert parsed["league"]["lineup"] == {
        "QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "DEF": 1, "D": 1,
    }
    assert parsed["league"]["bench"] == 6
    assert parsed["league"]["ir_slots"] == 2
    assert parsed["league"]["playoff_weeks"] == [15, 16, 17]
    assert parsed["league"]["playoff_reseeding"] is True
    assert parsed["league"]["waiver_type"] == "rolling"
    assert parsed["scoring"]["pass_td"] == 6
    assert parsed["scoring"]["pass_int"] == -2
    assert parsed["scoring"]["def_fourth_down_stop"] == 2
    assert parsed["scoring"]["def_xp_return"] == 2
    assert parsed["scoring"]["def_sack"] == 1
    assert parsed["idp_scoring"]["tackle_solo"] == 1
    assert parsed["idp_scoring"]["sack"] == 2


def test_parse_roster_and_match_normalized_names():
    roster = parse_roster_text((FIXTURES / "yahoo_roster_fake.txt").read_text())
    players = pl.DataFrame({
        "player_id": ["p1", "p2", "p3"],
        "full_name": ["Jose Test", "Sample Runner", "Other"],
        "position": ["QB", "RB", "WR"],
        "team": ["LAR", "CLE", "BAL"],
    })

    matched, unmatched = match_roster(roster, players)

    assert normalize_player_name("José Test Jr.") == "jose test"
    assert matched.filter(pl.col("name") == "José Test Jr.").item(0, "sleeper_id") == "p1"
    assert matched.filter(pl.col("pos") == "DEF").item(0, "sleeper_id") == "DEN"
    assert matched.filter(pl.col("name") == "Sample Runner III").item(0, "match_method") == "name+position+team"
    assert unmatched.is_empty()
    assert matched.filter(pl.col("slot") == "D").item(0, "model_excluded") is True


def test_parse_available_text_handles_concatenated_yahoo_pages():
    available, unparsed = parse_available_text(
        (FIXTURES / "yahoo_available_fake.txt").read_text()
    )

    assert available.to_dicts() == [
        {"name": "Alpha Runner", "nfl_team": "SEA", "pos": "RB"},
        {"name": "Beta Catcher", "nfl_team": "NE", "pos": "WR"},
        {"name": "Gamma Stash", "nfl_team": "NO", "pos": "WR"},
        {"name": "Comets", "nfl_team": "DEN", "pos": "DEF"},
    ]
    assert "This line cannot be parsed" in unparsed
