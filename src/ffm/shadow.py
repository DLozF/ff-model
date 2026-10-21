"""Leakage-free shadow projection snapshots and scoring."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
from scipy.stats import spearmanr

from ffm.backtest import pinball_crps

TEST_WEEKS = tuple(range(7, 13))
CANDIDATES = ("sleeper", "def_stop", "expanded_ridge")


def shadow_snapshot_path(root: str | Path, season: int, week: int) -> Path:
    """Return the exact user-facing weekly shadow artifact path."""
    return Path(root) / "data/shadow" / f"{int(season)}_w{int(week)}.parquet"


def overlay_snapshot_points(
    frame: pl.DataFrame,
    snapshots: pl.DataFrame,
    candidate: str,
    projection_column: str,
) -> pl.DataFrame:
    """Restore immutable pregame points when rebuilding prior shadow weeks."""
    points = snapshots.filter(pl.col("candidate") == candidate).select(
        "season", "week", "sleeper_id", pl.col("proj_pts").alias("_shadow_point")
    )
    return (
        frame.join(points, on=["season", "week", "sleeper_id"], how="left")
        .with_columns(
            pl.coalesce(pl.col("_shadow_point"), pl.col(projection_column))
            .alias(projection_column)
        )
        .drop("_shadow_point")
    )


def week_key(season: int, week: int) -> int:
    return int(season) * 100 + int(week)


def training_before(
    frame: pl.DataFrame, candidate_column: str, season: int, week: int
) -> pl.DataFrame:
    """Return a candidate's played training rows strictly before the target week."""
    return (
        frame.filter(
            pl.col("played")
            & (pl.col("season") * 100 + pl.col("week") < week_key(season, week))
        )
        .drop("proj_pts")
        .rename({candidate_column: "proj_pts"})
    )


def first_kickoff_utc(schedules: pl.DataFrame, season: int, week: int) -> datetime:
    """Return the first regular-season kickoff; nflverse game times are Eastern."""
    games = schedules.filter(
        (pl.col("season") == season)
        & (pl.col("week") == week)
        & (pl.col("game_type") == "REG")
    )
    if games.is_empty():
        raise ValueError(f"no schedule for {season} week {week}")
    kickoffs = []
    for row in games.select("gameday", "gametime").iter_rows(named=True):
        local = datetime.strptime(
            f"{row['gameday']} {row['gametime']}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=ZoneInfo("America/New_York"))
        kickoffs.append(local.astimezone(timezone.utc))
    return min(kickoffs)


def write_snapshot_once(path: str | Path, frame: pl.DataFrame) -> bool:
    """Atomically create an immutable snapshot; never overwrite an existing week."""
    path = Path(path)
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.write_parquet(temporary)
    os.replace(temporary, path)
    return True


def write_snapshot_before_kickoff(
    path: str | Path,
    frame: pl.DataFrame,
    kickoff: datetime,
    now: datetime,
) -> bool:
    """Create a snapshot only while the pregame deadline is still open."""
    if Path(path).exists():
        return False
    if now.astimezone(timezone.utc) >= kickoff.astimezone(timezone.utc):
        raise RuntimeError(f"shadow snapshot deadline passed: {kickoff.isoformat()}")
    return write_snapshot_once(path, frame)


def score_shadow_snapshot(
    snapshot: pl.DataFrame, actuals: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Score one completed shadow week by position and as a sample-weighted total."""
    scored = snapshot.join(
        actuals.filter(pl.col("played")).select("season", "week", "sleeper_id", "act_pts"),
        on=["season", "week", "sleeper_id"], how="inner",
    )
    position_rows = []
    for group in scored.partition_by(["season", "week", "candidate", "pos"], as_dict=False):
        actual = group.get_column("act_pts").to_numpy()
        projected = group.get_column("proj_pts").to_numpy()
        levels = np.asarray(group.item(0, "quantile_levels"), dtype=float)
        quantiles = np.vstack(group.get_column("quantiles").to_list())
        coefficient = float("nan")
        if group.height >= 3 and np.unique(actual).size > 1 and np.unique(projected).size > 1:
            coefficient = float(spearmanr(actual, projected).statistic)
        position_rows.append({
            "season": int(group.item(0, "season")),
            "week": int(group.item(0, "week")),
            "candidate": group.item(0, "candidate"),
            "pos": group.item(0, "pos"),
            "n": group.height,
            "spearman": coefficient,
            "crps": float(pinball_crps(actual, quantiles, levels).mean()),
        })
    position = pl.from_dicts(position_rows)
    weekly_rows = []
    for group in position.partition_by(["season", "week", "candidate"], as_dict=False):
        valid = group.filter(pl.col("spearman").is_not_nan())
        weekly_rows.append({
            "season": int(group.item(0, "season")),
            "week": int(group.item(0, "week")),
            "candidate": group.item(0, "candidate"),
            "n": int(group.get_column("n").sum()),
            "spearman": (
                float(np.average(valid["spearman"], weights=valid["n"]))
                if not valid.is_empty() else float("nan")
            ),
            "crps": float(np.average(group["crps"], weights=group["n"])),
        })
    return position, pl.from_dicts(weekly_rows)


def adoption_status(weekly: pl.DataFrame) -> dict[str, dict]:
    """Apply the frozen 4-of-6 Spearman and +0.5% total-CRPS rule."""
    baseline = weekly.filter(pl.col("candidate") == "sleeper").select(
        "week", pl.col("spearman").alias("baseline_spearman")
    )
    baseline_rows = weekly.filter(pl.col("candidate") == "sleeper")
    baseline_crps = (
        float(np.average(baseline_rows["crps"], weights=baseline_rows["n"]))
        if not baseline_rows.is_empty() else float("nan")
    )
    complete = set(baseline_rows.get_column("week").to_list()) == set(TEST_WEEKS)
    result = {}
    for candidate in CANDIDATES[1:]:
        rows = weekly.filter(pl.col("candidate") == candidate).join(baseline, on="week", how="inner")
        wins = int((rows.get_column("spearman") > rows.get_column("baseline_spearman")).sum())
        candidate_crps = (
            float(np.average(rows["crps"], weights=rows["n"]))
            if not rows.is_empty() else float("nan")
        )
        guard = bool(np.isfinite(candidate_crps) and np.isfinite(baseline_crps) and candidate_crps <= baseline_crps * 1.005)
        result[candidate] = {
            "weeks_scored": rows.height,
            "spearman_wins": wins,
            "crps": candidate_crps,
            "baseline_crps": baseline_crps,
            "crps_guard": guard,
            "eligible": bool(complete and rows.height == 6 and wins >= 4 and guard),
            "decision": "eligible" if complete and rows.height == 6 and wins >= 4 and guard else "rejected" if complete else "pending",
        }
    return result
