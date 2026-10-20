from ffm.market import acceptance_label, market_ratio, package_value


def test_henry_for_coker_and_monangai_is_unlikely():
    coker_monangai = package_value([2043.0, 1214.0])
    henry = package_value([7144.0])

    ratio = market_ratio(receives=coker_monangai, gives=henry)

    assert acceptance_label(ratio) == "UNLIKELY"


def test_exact_swap_is_likely():
    ratio = market_ratio(receives=package_value([5000.0]), gives=package_value([5000.0]))

    assert ratio == 1.0
    assert acceptance_label(ratio) == "LIKELY"