import polars as pl
import pytest

from ffm.market_fallback import apply_model_fallback, fit_replacement_index


def _market(**rows):
    base = {
        "player_sleeperId": [], "player_name": [], "player_position": [],
        "player_maybeTeam": [], "redraftValue": [],
    }
    base.update(rows)
    return pl.DataFrame(base)


def _players(**rows):
    base = {
        "player_index": [], "player_id": [], "ros_points": [], "name": [],
        "position": [], "team": [],
    }
    base.update(rows)
    return pl.DataFrame(base)


def test_unmatched_healthy_skill_player_gets_positive_value():
    players = _players(
        player_index=list(range(18)),
        player_id=[
            "r1", "r2", "r3", "r4", "r5",
            "t1", "t2", "t3", "t4", "t5",
            "w1", "w2", "w3", "w4", "w5",
            "u1", "u2", "u3",
        ],
        ros_points=[
            300.0, 250.0, 200.0, 150.0, 120.0,
            290.0, 240.0, 190.0, 140.0, 110.0,
            295.0, 245.0, 195.0, 145.0, 115.0,
            180.0, 175.0, 185.0,
        ],
        name=(
            [f"Matched RB {i}" for i in range(5)]
            + [f"Matched TE {i}" for i in range(5)]
            + [f"Matched WR {i}" for i in range(5)]
            + ["AJ Barner", "Tyrone Tracy", "Deep Bench"]
        ),
        position=["RB"] * 5 + ["TE"] * 5 + ["WR"] * 5 + ["TE", "RB", "WR"],
        team=["SEA"] * 18,
    )
    market = _market(
        player_sleeperId=[
            "r1", "r2", "r3", "r4", "r5",
            "t1", "t2", "t3", "t4", "t5",
            "w1", "w2", "w3", "w4", "w5",
        ],
        player_name=(
            [f"Matched RB {i}" for i in range(5)]
            + [f"Matched TE {i}" for i in range(5)]
            + [f"Matched WR {i}" for i in range(5)]
        ),
        player_position=["RB"] * 5 + ["TE"] * 5 + ["WR"] * 5,
        player_maybeTeam=["SEA"] * 15,
        redraftValue=[5000.0, 4000.0, 3000.0, 2000.0, 1000.0] * 3,
    )
    sleeper = pl.DataFrame({"player_id": ["u1", "u2", "u3"], "injury_status": [None] * 3, "status": ["Active"] * 3})

    result = apply_model_fallback(players, market, sleeper)

    unmatched = result.filter(pl.col("player_id").is_in(["u1", "u2", "u3"]))
    assert unmatched.get_column("market_value_final").min() > 0
    assert set(unmatched.get_column("value_source")) == {"model_fallback"}


def test_kicker_and_defense_values_stay_below_lowest_matched_flex_value():
    players = _players(
        player_index=list(range(7)),
        player_id=["m1", "m2", "m3", "m4", "m5", "k1", "d1"],
        ros_points=[300.0, 250.0, 200.0, 150.0, 120.0, 100.0, 90.0],
        name=["M1", "M2", "M3", "M4", "M5", "Will Reichard", "Vikings D"],
        position=["RB", "RB", "RB", "RB", "RB", "K", "DEF"],
        team=["SEA"] * 7,
    )
    market = _market(
        player_sleeperId=["m1", "m2", "m3", "m4", "m5"],
        player_name=["M1", "M2", "M3", "M4", "M5"],
        player_position=["RB"] * 5,
        player_maybeTeam=["SEA"] * 5,
        redraftValue=[5000.0, 4000.0, 3000.0, 2000.0, 2.0],
    )
    sleeper = pl.DataFrame({"player_id": ["k1", "d1"], "injury_status": [None, None], "status": ["Active", "Active"]})

    result = apply_model_fallback(players, market, sleeper)

    kicker = result.filter(pl.col("player_id") == "k1")
    defense = result.filter(pl.col("player_id") == "d1")
    assert kicker.get_column("market_value_final").item() <= 2.0
    assert defense.get_column("market_value_final").item() <= 2.0


def test_out_for_season_player_gets_zero_value():
    players = _players(
        player_index=list(range(2)),
        player_id=["u1", "m1"],
        ros_points=[300.0, 200.0],
        name=["Jalen Hurts", "M1"],
        position=["QB", "RB"],
        team=["PHI", "SEA"],
    )
    market = _market(
        player_sleeperId=["m1"], player_name=["M1"], player_position=["RB"],
        player_maybeTeam=["SEA"], redraftValue=[2000.0],
    )
    sleeper = pl.DataFrame({"player_id": ["u1", "m1"], "injury_status": ["IR", None], "status": ["Inactive", "Active"]})

    result = apply_model_fallback(players, market, sleeper)

    row = result.filter(pl.col("player_id") == "u1")
    assert row.get_column("market_value_final").item() == 0.0
    assert row.get_column("value_source").item() == "out"
    assert row.get_column("injury_status").item() == "IR"


def test_second_pass_matches_by_name_position_and_team():
    players = _players(
        player_index=[0],
        player_id=["not-on-market"],
        ros_points=[180.0],
        name=["Greg Dulcich"],
        position=["TE"],
        team=["DEN"],
    )
    market = _market(
        player_sleeperId=["999999"],
        player_name=["Greg Dulcich"],
        player_position=["TE"],
        player_maybeTeam=["DEN"],
        redraftValue=[1500.0],
    )
    sleeper = pl.DataFrame({"player_id": ["not-on-market"], "injury_status": [None], "status": ["Active"]})

    result = apply_model_fallback(players, market, sleeper)

    assert result.get_column("market_value_final").item() == 1500.0
    assert result.get_column("value_source").item() == "name_match"


def test_second_pass_never_matches_across_positions_or_teams():
    players = _players(
        player_index=[0],
        player_id=["not-on-market"],
        ros_points=[180.0],
        name=["Greg Dulcich"],
        position=["TE"],
        team=["NYG"],
    )
    market = _market(
        player_sleeperId=["999999"],
        player_name=["Greg Dulcich"],
        player_position=["TE"],
        player_maybeTeam=["DEN"],
        redraftValue=[1500.0],
    )
    sleeper = pl.DataFrame({"player_id": ["not-on-market"], "injury_status": [None], "status": ["Active"]})

    result = apply_model_fallback(players, market, sleeper)

    assert result.get_column("value_source").item() == "model_fallback"
    assert result.get_column("market_value_final").item() < 1500.0


def test_replacement_index_uses_lineup_needs():
    players = _players(
        player_index=list(range(6)),
        player_id=["1", "2", "3", "4", "5", "6"],
        ros_points=[50.0, 40.0, 30.0, 20.0, 10.0, 5.0],
        name=list("ABCDEF"),
        position=["RB"] * 6,
        team=["SEA"] * 6,
    )

    index = fit_replacement_index(players, lineup={"RB": 2, "FLEX": 1})

    assert index["RB"] == 2  # third-highest RB is the replacement


def test_value_source_column_exposes_all_sources():
    players = _players(
        player_index=[0, 1, 2, 3, 4, 5],
        player_id=["m1", "m2", "m3", "m4", "m5", "u1"],
        ros_points=[300.0, 250.0, 200.0, 150.0, 120.0, 80.0],
        name=["M1", "M2", "M3", "M4", "M5", "Injured Guy"],
        position=["WR"] * 6,
        team=["SEA"] * 6,
    )
    market = _market(
        player_sleeperId=["m1", "m2", "m3", "m4", "m5"],
        player_name=["M1", "M2", "M3", "M4", "M5"],
        player_position=["WR"] * 5,
        player_maybeTeam=["SEA"] * 5,
        redraftValue=[5000.0, 4000.0, 3000.0, 2000.0, 1000.0],
    )
    sleeper = pl.DataFrame({"player_id": ["u1"], "injury_status": ["Out"], "status": ["Inactive"]})

    result = apply_model_fallback(players, market, sleeper)

    assert set(result.get_column("value_source")) <= {"fantasycalc", "name_match", "model_fallback", "out"}
    assert result.filter(pl.col("value_source") == "fantasycalc").height == 5
    assert result.filter(pl.col("value_source") == "out").height == 1
