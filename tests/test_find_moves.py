from datetime import date

import numpy as np

from scripts.find_moves import (
    availability_warning, bye_coverage_gaps, eligible_waiver_candidates,
    trades_open,
)


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
