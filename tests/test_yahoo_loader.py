import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import polars as pl
import pytest
import yaml

from ffm.yahoo_loader import YahooTableError, load_yahoo_payload, parse_yahoo_payload


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


def base_config():
    return {
        "league": {
            "teams": 12, "lineup": {"QB": 1}, "bench": 6,
            "regular_season_weeks": [1, 14], "playoff_teams": 6,
            "playoff_weeks": [15, 16, 17], "partial_import": True,
            "waiver_type": "rolling", "trade_deadline": "November 28, 2026",
            "playoff_reseeding": True,
        },
        "scoring": {
            "pass_td": 6.0,
            "pass_yd_milestones": [{"threshold": 300, "points": 2.0}],
            "pass_cmp_40p": 1.0,
            "def_fourth_down_stop": 2.0,
        },
        "idp_scoring": {"tackle_solo": 1.0},
    }


def test_load_preserves_settings_omitted_by_api(tmp_path):
    payload = json.loads((Path(__file__).parent / "fixtures/yahoo_fake.json").read_text())
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(base_config(), sort_keys=False))

    load_yahoo_payload(
        payload, pl.DataFrame(), config_path, tmp_path / "cache",
        tmp_path / "yahoo_load_diff.md", now=datetime(2026, 10, 21, 12, 0, 0),
    )

    config = yaml.safe_load(config_path.read_text())
    assert config["scoring"]["pass_yd_milestones"] == [
        {"threshold": 300, "points": 2.0}
    ]
    assert config["scoring"]["pass_cmp_40p"] == 1.0
    assert config["scoring"]["def_fourth_down_stop"] == 2.0
    assert config["idp_scoring"] == {"tackle_solo": 1.0}
    assert config["league"]["waiver_type"] == "rolling"
    assert config["league"]["playoff_reseeding"] is True
    assert config["league"]["partial_import"] is True
    assert list(tmp_path.glob("config.yaml.pre-yahoo-*"))


def test_load_keeps_conflicting_pasted_value_and_reports_it(tmp_path):
    payload = json.loads((Path(__file__).parent / "fixtures/yahoo_fake.json").read_text())
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(base_config(), sort_keys=False))
    diff_path = tmp_path / "yahoo_load_diff.md"

    load_yahoo_payload(
        payload, pl.DataFrame(), config_path, tmp_path / "cache", diff_path,
        now=datetime(2026, 10, 21, 12, 0, 0),
    )

    assert yaml.safe_load(config_path.read_text())["scoring"]["pass_td"] == 6.0
    diff = diff_path.read_text()
    assert "scoring.pass_td" in diff
    assert "existing: `6.0`" in diff
    assert "Yahoo API: `4.0`" in diff


def test_broken_standings_leaves_config_byte_identical(tmp_path):
    payload = json.loads((Path(__file__).parent / "fixtures/yahoo_fake.json").read_text())
    broken = deepcopy(payload)
    broken["standings"] = [{"team_id": 1, "rank": 1}]
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(base_config(), sort_keys=False))
    before = config_path.read_bytes()

    with pytest.raises(YahooTableError, match="standings"):
        load_yahoo_payload(
            broken, pl.DataFrame(), config_path, tmp_path / "cache",
            tmp_path / "yahoo_load_diff.md",
            now=datetime(2026, 10, 21, 12, 0, 0),
        )

    assert config_path.read_bytes() == before
    assert not list(tmp_path.glob("config.yaml.pre-yahoo-*"))
