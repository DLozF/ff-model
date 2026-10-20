from datetime import date

from scripts.find_moves import eligible_waiver_candidates, trades_open


def test_trades_close_after_configured_deadline():
    assert trades_open("November 28, 2026", date(2026, 11, 28)) is True
    assert trades_open("November 28, 2026", date(2026, 11, 29)) is False


def test_waiver_candidates_protect_current_ir_players():
    assert list(eligible_waiver_candidates([9], [1, 2], {2})) == [(1, 9)]
