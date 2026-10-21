from datetime import datetime

import polars as pl
import pytest

from ffm.market import (
    acceptance_cutoffs, acceptance_label, acceptance_status, load_market,
    healthy_market_fallers, market_ratio, package_value, write_model_vs_market,
)


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


def test_acceptance_cutoffs_stay_default_below_twenty_resolved_rows(tmp_path):
    path = tmp_path / "trade_log.csv"
    path.write_text(
        "date,my_team_gives,my_team_gets,partner,r,model_verdict,outcome\n"
        "2026-10-20,A,B,Team 2,1.1,ACCEPT,accepted\n",
        encoding="utf-8",
    )

    cutoffs = acceptance_cutoffs(path)

    assert cutoffs["calibrated"] is False
    assert cutoffs["resolved"] == 1
    assert acceptance_label(0.95, cutoffs) == "POSSIBLE"
    assert "1/20 resolved offers" in acceptance_status(cutoffs)


def test_acceptance_cutoffs_fit_after_twenty_resolved_rows(tmp_path):
    path = tmp_path / "trade_log.csv"
    rows = ["date,my_team_gives,my_team_gets,partner,r,model_verdict,outcome"]
    for index in range(10):
        rows.append(f"2026-10-20,A,B,Team 2,{0.60 + index * 0.02:.2f},ACCEPT,rejected")
    for index in range(10):
        rows.append(f"2026-10-20,A,B,Team 2,{1.10 + index * 0.02:.2f},ACCEPT,accepted")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    cutoffs = acceptance_cutoffs(path)

    assert cutoffs["calibrated"] is True
    assert cutoffs["resolved"] == 20
    assert cutoffs["likely"] > cutoffs["possible"]


def test_write_model_vs_market_preserves_forward_test_section(tmp_path):
    path = tmp_path / "model_vs_market.md"
    path.write_text(
        "old\n<!-- forward-test:start -->\nkept\n<!-- forward-test:end -->\n",
        encoding="utf-8",
    )
    players = pl.DataFrame({
        "player_id": ["1"], "name": ["Player"], "position": ["RB"],
        "ros_points": [100.0],
    })
    market = pl.DataFrame({
        "sleeper_id": ["1"], "market_value": [1000.0],
        "market_position_rank": [1],
    })

    write_model_vs_market(players, market, path)

    text = path.read_text(encoding="utf-8")
    assert "kept" in text
    assert text.count("<!-- forward-test:start -->") == 1


def test_healthy_market_fallers_uses_prior_value_as_percent_base():
    market = pl.DataFrame({
        "sleeper_id": ["1"],
        "market_name": ["Faller"],
        "market_position": ["WR"],
        "market_value": [37.0],
        "trend_30_day": [-181.0],
    })
    players = pl.DataFrame({
        "player_id": ["1"], "injury_status": [None],
        "status": ["Active"], "active": [True],
    })

    result = healthy_market_fallers(market, players, {"1"})

    assert result.height == 1
    assert result.get_column("trend_pct").item() == pytest.approx(-83.0275, abs=0.001)


def test_healthy_market_fallers_skips_nonpositive_prior_value():
    market = pl.DataFrame({
        "sleeper_id": ["1"],
        "market_name": ["Invalid Riser"],
        "market_position": ["RB"],
        "market_value": [10.0],
        "trend_30_day": [20.0],
    })
    players = pl.DataFrame({
        "player_id": ["1"], "injury_status": [None],
        "status": ["Active"], "active": [True],
    })

    result = healthy_market_fallers(market, players, {"1"})

    assert result.is_empty()