from math import comb

from ffm.finder import trade_candidates, waiver_candidates


def test_trade_candidates_cover_all_requested_shapes():
    candidates = list(trade_candidates([1, 2, 3], [4, 5, 6]))
    assert len(candidates) == 3 * 3 + comb(3, 2) * 3 + 3 * comb(3, 2)
    assert any(len(give) == 2 and len(get) == 1 for give, get in candidates)
    assert any(len(give) == 1 and len(get) == 2 for give, get in candidates)


def test_waiver_candidates_are_cartesian_product():
    assert list(waiver_candidates([10, 11], [1, 2])) == [
        (1, 10), (2, 10), (1, 11), (2, 11)
    ]
