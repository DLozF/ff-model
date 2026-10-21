import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from scripts.find_moves import (
    availability_warning, best_drop_per_add, bye_coverage_gaps, drop_is_allowed,
    current_available_pool, eligible_waiver_candidates, priority_advice,
    trades_open,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_trades_close_after_configured_deadline():
    assert trades_open("November 28, 2026", date(2026, 11, 28)) is True
    assert trades_open("November 28, 2026", date(2026, 11, 29)) is False


def test_waiver_candidates_protect_current_ir_players():
    assert list(eligible_waiver_candidates([9], [1, 2], {2})) == [(1, 9)]


def test_bye_coverage_gaps_counts_missing_base_slots():
    projections = np.array([
        [10.0, 8.0, 0.0],
        [0.0, 8.0, 7.0],
    ])
    positions = np.array(["QB", "RB", "RB"])

    gaps = bye_coverage_gaps(
        projections, positions, [0, 1, 2], {"QB": 1, "RB": 2}
    )

    assert gaps == 2


def test_partial_import_without_recent_available_file_warns(tmp_path):
    warning = availability_warning(tmp_path, True, date(2026, 10, 21))

    assert warning == "confirm the player is available on Yahoo before claiming"


def test_best_drop_per_add_keeps_one_row_per_distinct_add():
    rows = [
        (3.0, 1, 10, [10]),
        (2.0, 2, 10, [10]),
        (1.0, 3, 11, [11]),
    ]

    assert best_drop_per_add(rows, limit=10) == [rows[0], rows[2]]


def test_drop_protection_requires_large_playoff_gain_for_valuable_player():
    assert drop_is_allowed(300.0, 0.049, protected_ir=False) is False
    assert drop_is_allowed(300.0, 0.050, protected_ir=False) is True
    assert drop_is_allowed(0.0, 0.100, protected_ir=True) is False


def test_priority_advice_requires_gain_and_starting_role():
    assert priority_advice(0.03, "starting") == "worth using priority"
    assert priority_advice(0.03, "bye-week starter") == "worth using priority"
    assert priority_advice(0.029, "starting") == "depth only, skip"
    assert priority_advice(0.10, "depth") == "depth only, skip"


def test_recent_available_file_is_the_only_free_agent_pool(tmp_path):
    paste = tmp_path / "data/yahoo_paste"
    paste.mkdir(parents=True)
    available = paste / "available.txt"
    available.write_text((FIXTURES / "yahoo_available_fake.txt").read_text())
    timestamp = datetime(2026, 10, 20, tzinfo=ZoneInfo("America/Chicago")).timestamp()
    os.utime(available, (timestamp, timestamp))
    players = pl.DataFrame({
        "player_index": [0, 1, 2, 3, 4],
        "player_id": ["a", "b", "c", "d", "e"],
        "name": ["Alpha Runner", "Beta Catcher", "Gamma Stash", "Comets", "Other"],
        "position": ["RB", "WR", "WR", "DEF", "QB"],
        "team": ["SEA", "NE", "NO", "DEN", "NYG"],
    })

    pool, estimated = current_available_pool(
        tmp_path, date(2026, 10, 21), players, fallback=[4]
    )

    assert pool == [0, 1, 2, 3]
    assert estimated is False
    assert "This line cannot be parsed" in (
        tmp_path / "logs/available_unparsed.log"
    ).read_text()
