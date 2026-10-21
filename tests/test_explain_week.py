import json
from pathlib import Path

from scripts.explain_week import actual_breakdown, pregame_features, resolve_player
import polars as pl
import numpy as np

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"


def test_resolve_player_is_unique_for_plain_names():
    players = pl.read_parquet(CACHE / "sleeper_players.parquet").filter(
        pl.col("position").is_in(("QB", "RB", "WR", "TE", "K", "DEF"))
    )

    player, candidates = resolve_player("Malik Nabers", players)

    assert player is not None
    assert player["position"] == "WR"
    assert candidates == []


def test_actual_breakdown_scores_receptions_milestones_and_bonuses():
    stats = pl.read_parquet(CACHE / "nflverse_player_stats.parquet")
    pbp = pl.concat(
        [pl.read_parquet(path) for path in sorted(CACHE.glob("nflverse_pbp_bonus_*.parquet"))],
        how="diagonal_relaxed",
    )
    frame = pl.read_parquet(CACHE / "player_weeks.parquet")
    row = frame.filter((pl.col("name") == "Malik Nabers") & (pl.col("season") == 2026) & (pl.col("week") == 4)).row(0, named=True)
    player = {**row, "gsis_id": "00-0039337"}

    actual = actual_breakdown(player, stats, pbp, pl.DataFrame())

    assert actual["played"] is True
    assert actual["total"] > 20.0
    assert actual["rec"] == 6
    assert actual["rec_yd"] == 112
    assert actual["rec_td"] == 1


def test_pregame_features_never_read_target_week_data():
    frame = pl.read_parquet(CACHE / "player_weeks.parquet")
    row = frame.filter((pl.col("name") == "Malik Nabers") & (pl.col("season") == 2026) & (pl.col("week") == 4)).row(0, named=True)
    snaps = pl.read_parquet(CACHE / "nflverse_snap_counts.parquet")
    opportunity = pl.read_parquet(CACHE / "nflverse_ff_opportunity.parquet")
    schedules = pl.read_parquet(CACHE / "nflverse_schedules.parquet")
    injuries = pl.read_parquet(CACHE / "nflverse_injuries.parquet")
    player = {**row, "gsis_id": "00-0039337"}

    features = pregame_features(player, frame, snaps, opportunity, schedules, injuries)

    assert features["snap_share"] >= 0.0
    assert features["team_implied_points"] > 0.0
