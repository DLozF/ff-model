from datetime import datetime

import polars as pl

from ffm.market import acceptance_label, load_market, market_ratio, package_value


def test_henry_for_coker_and_monangai_is_unlikely():
    coker_monangai = package_value([2043.0, 1214.0])
    henry = package_value([7144.0])

    ratio = market_ratio(receives=coker_monangai, gives=henry)

    assert acceptance_label(ratio) == "UNLIKELY"


def test_exact_swap_is_likely():
    ratio = market_ratio(receives=package_value([5000.0]), gives=package_value([5000.0]))

    assert ratio == 1.0
    assert acceptance_label(ratio) == "LIKELY"


def test_load_market_accepts_legacy_maybe_team_column(tmp_path):
    now = datetime(2026, 10, 20)
    pl.DataFrame({
        "fetched_at": [now],
        "player_sleeperId": ["1"],
        "player_name": ["Player"],
        "player_position": ["TE"],
        "player_maybeTeam": ["SEA"],
        "redraftValue": [100],
        "trend30Day": [0],
        "overallRank": [1],
        "positionRank": [1],
    }).write_parquet(tmp_path / "fantasycalc_values_2026-10-20.parquet")

    market = load_market(tmp_path, now)

    assert market.get_column("market_team").item() == "SEA"