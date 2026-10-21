import numpy as np
import polars as pl

from ffm.own_projection import build_context_features, build_features, ewma, fit_half_life


def test_ewma_recent_points_weight_more():
    assert ewma(np.array([0.0, 10.0]), 0.5) > ewma(np.array([0.0, 10.0]), 4.0)
    assert ewma(np.array([10.0, 0.0]), 0.5) < ewma(np.array([10.0, 0.0]), 4.0)
    assert ewma(np.array([]), 2.0) == 0.0


def test_fit_half_life_returns_per_position_values():
    frame = pl.DataFrame({
        "season": [2022, 2022, 2022], "week": [1, 2, 3], "pos": ["QB", "QB", "QB"],
        "sleeper_id": ["a", "a", "a"], "act_pts": [10.0, 20.0, 5.0],
    })

    half_lives = fit_half_life(frame)

    assert half_lives["QB"] in (1.0, 2.0, 3.0, 4.0, 6.0, 8.0)


def test_build_features_never_uses_same_week_data():
    frame = pl.DataFrame({
        "season": [2023, 2023], "week": [1, 2], "sleeper_id": ["a", "a"], "pos": ["QB", "QB"],
        "team": ["TB", "TB"], "act_pts": [10.0, 30.0], "proj_pts": [15.0, 18.0],
        "played": [True, True],
    })

    features = build_features(frame)

    week2 = features.filter(pl.col("week") == 2)
    assert week2.item(0, "ewma") > 0.0
    assert week2.item(0, "last3") == 10.0
    week1 = features.filter(pl.col("week") == 1)
    assert week1.item(0, "last3") == 0.0


def test_context_features_are_pregame_team_shares_and_qb_change():
    frame = pl.DataFrame({
        "season": [2023] * 5,
        "week": [1, 1, 1, 2, 2],
        "sleeper_id": ["wr", "qb1", "other", "wr", "qb2"],
        "gsis_id": ["g-wr", "g-qb1", "g-other", "g-wr", "g-qb2"],
        "pos": ["WR", "QB", "WR", "WR", "QB"],
        "team": ["TB", "TB", "NYJ", "TB", "TB"],
        "opp": ["MIN", "MIN", "ATL", "ATL", "ATL"],
        "act_pts": [12.0, 20.0, 16.0, 99.0, 99.0],
        "proj_pts": [10.0, 18.0, 11.0, 13.0, 17.0],
        "played": [True] * 5,
    })
    stats = pl.DataFrame({
        "season": [2023] * 6, "week": [1, 1, 1, 1, 2, 2],
        "player_id": ["g-wr", "g-qb1", "g-rb", "g-other", "g-wr", "g-qb2"],
        "team": ["TB", "TB", "TB", "NYJ", "TB", "TB"],
        "targets": [10.0, 0.0, 0.0, 8.0, 40.0, 0.0],
        "carries": [1.0, 2.0, 20.0, 0.0, 50.0, 3.0],
        "attempts": [0.0, 40.0, 0.0, 35.0, 0.0, 50.0],
    })
    snaps = pl.DataFrame({
        "season": [2023, 2023], "week": [1, 2],
        "pfr_player_id": ["p-wr", "p-wr"], "offense_pct": [0.80, 0.05],
    })
    mapping = pl.DataFrame({"pfr_id": ["p-wr"], "gsis_id": ["g-wr"]})
    schedules = pl.DataFrame({
        "season": [2023, 2023], "week": [1, 2], "game_type": ["REG", "REG"],
        "home_team": ["MIN", "TB"], "away_team": ["TB", "ATL"],
        "total_line": [44.0, 46.0], "spread_line": [2.0, 4.0],
    })

    features = build_context_features(frame, stats, snaps, mapping, schedules)
    week2 = features.filter((pl.col("week") == 2) & (pl.col("sleeper_id") == "wr"))

    assert week2.item(0, "snap_share") == 0.80
    assert week2.item(0, "target_share") == 0.25
    assert abs(week2.item(0, "carry_share") - (1 / 23)) < 1e-12
    assert week2.item(0, "team_implied_points") == 25.0
    assert week2.item(0, "spread") == 4.0
    assert week2.item(0, "home") == 1.0
    assert week2.item(0, "qb_change") == 1.0
    assert week2.item(0, "opponent_pos_allowed") > 0.0


def test_build_features_can_emit_unplayed_target_without_using_target_actual():
    frame = pl.DataFrame({
        "season": [2026, 2026], "week": [6, 7], "sleeper_id": ["a", "a"],
        "pos": ["WR", "WR"], "team": ["TB", "TB"], "opp": ["ATL", "CAR"],
        "gsis_id": ["g-a", "g-a"], "act_pts": [12.0, 999.0],
        "proj_pts": [10.0, 14.0], "played": [True, False],
    })

    features = build_features(frame, half_lives={"WR": 2.0}, include_unplayed=True)
    target = features.filter(pl.col("week") == 7)

    assert target.item(0, "last3") == 12.0
    assert target.item(0, "season_avg") == 12.0
    assert target.item(0, "played") is False
