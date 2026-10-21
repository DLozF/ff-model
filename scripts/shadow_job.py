"""Create immutable shadow projections and score completed shadow weeks."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import numpy as np
import polars as pl

from ffm.backtest_projection import EXPANDED_FEATURES, train_expanded_ridge, walk_forward_expanded
from ffm.config import load_config
from ffm.distributions import POSITIONS, QuantileModel
from ffm.expected_bonus import defense_bonus, prior_rows
from ffm.ids import normalize_team
from ffm.own_projection import build_context_features
from ffm.scoring import score_projection_frame
from ffm.shadow import (
    CANDIDATES,
    TEST_WEEKS,
    adoption_status,
    first_kickoff_utc,
    overlay_snapshot_points,
    score_shadow_snapshot,
    shadow_snapshot_path,
    training_before,
    write_snapshot_before_kickoff,
)


def current_projection_rows(root: Path, frame: pl.DataFrame, scoring: dict, season: int, week: int) -> pl.DataFrame:
    """Use the refreshed Sleeper file while retaining the audited player-week universe."""
    path = root / "data/cache" / f"sleeper_projections_{season}_w{week:02d}.parquet"
    fresh = score_projection_frame(pl.read_parquet(path), scoring).select(
        pl.col("player_id").cast(pl.String).alias("sleeper_id"),
        pl.col("proj_pts").alias("fresh_proj_pts"),
    ).unique("sleeper_id", keep="last")
    target = frame.filter((pl.col("season") == season) & (pl.col("week") == week))
    return (
        target.join(fresh, on="sleeper_id", how="inner")
        .drop("proj_pts")
        .rename({"fresh_proj_pts": "proj_pts"})
        .with_columns(pl.lit(False).alias("played"), pl.lit(0.0).alias("act_pts"))
    )


def defense_attempt_history(cache: Path) -> pl.DataFrame:
    """Aggregate fourth-down attempts and stops by offense-defense game."""
    pbp = pl.concat(
        [pl.read_parquet(path) for path in sorted(cache.glob("nflverse_pbp_bonus_*.parquet"))],
        how="diagonal_relaxed",
    )
    return (
        pbp.filter(
            (pl.col("down") == 4)
            & (pl.col("punt_attempt").fill_null(0) != 1)
            & (pl.col("field_goal_attempt").fill_null(0) != 1)
            & pl.col("posteam").is_not_null()
            & pl.col("defteam").is_not_null()
        )
        .with_columns(
            pl.col("posteam").map_elements(normalize_team, return_dtype=pl.String).alias("offense"),
            pl.col("defteam").map_elements(normalize_team, return_dtype=pl.String).alias("defense"),
        )
        .group_by("season", "week", "offense", "defense")
        .agg(
            pl.len().cast(pl.Float64).alias("attempts"),
            pl.col("fourth_down_failed").fill_null(0).sum().cast(pl.Float64).alias("stops"),
        )
    )


def add_def_stop_projection(frame: pl.DataFrame, defense_weeks: pl.DataFrame, scoring: dict) -> pl.DataFrame:
    """Add only the expected defensive fourth-down-stop bonus, walk-forward."""
    ordered = frame.sort("season", "week", "sleeper_id")
    values = np.zeros(ordered.height, dtype=float)
    for season, week in ordered.select("season", "week").unique().sort("season", "week").iter_rows():
        selected = ordered.with_row_index("_row").filter(
            (pl.col("season") == season) & (pl.col("week") == week) & (pl.col("pos") == "DEF")
        )
        history = prior_rows(defense_weeks, int(season), int(week))
        for row in selected.iter_rows(named=True):
            values[int(row["_row"])] = defense_bonus(row, history, scoring)
    return ordered.with_columns(
        pl.Series("expected_def_stop_bonus", values),
        (pl.col("proj_pts") + pl.Series(values)).alias("def_stop"),
    )


def expanded_candidate_frames(
    frame: pl.DataFrame,
    stats: pl.DataFrame,
    snaps: pl.DataFrame,
    mapping: pl.DataFrame,
    schedules: pl.DataFrame,
    season: int,
    week: int,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Return historical walk-forward and current pregame expanded-ridge projections."""
    features = build_context_features(
        frame, stats, snaps, mapping, schedules, include_unplayed=True
    )
    prior_features = features.filter(
        pl.col("played")
        & (pl.col("season") * 100 + pl.col("week") < season * 100 + week)
    )
    historical = walk_forward_expanded(prior_features)
    target = features.filter((pl.col("season") == season) & (pl.col("week") == week))
    outputs = []
    for position in POSITIONS:
        rows = target.filter(pl.col("pos") == position)
        if rows.is_empty():
            continue
        model = train_expanded_ridge(position, prior_features)
        prediction = (
            model.predict(rows.select(EXPANDED_FEATURES).to_numpy())
            if model is not None else rows.get_column("proj_pts").to_numpy()
        )
        outputs.append(rows.with_columns(pl.Series("expanded_ridge", np.maximum(prediction, 0.0))))
    return historical, pl.concat(outputs).sort("sleeper_id")


def candidate_snapshot_rows(
    candidate: str,
    training: pl.DataFrame,
    target: pl.DataFrame,
    projection_column: str,
    created_at: datetime,
    kickoff: datetime,
) -> pl.DataFrame:
    """Fit candidate-specific quantiles and package long-format snapshot rows."""
    train = training_before(training, projection_column, int(target.item(0, "season")), int(target.item(0, "week")))
    model = QuantileModel.fit(train, k=500, smooth=9)
    records = []
    for position in POSITIONS:
        rows = target.filter(pl.col("pos") == position)
        if rows.is_empty() or position not in model.tables:
            continue
        projection = rows.get_column(projection_column).to_numpy()
        quantiles = model.quantile_matrix(position, projection)
        for row, value, row_quantiles in zip(rows.iter_rows(named=True), projection, quantiles):
            records.append({
                "season": int(row["season"]), "week": int(row["week"]),
                "sleeper_id": str(row["sleeper_id"]), "name": row.get("name"),
                "pos": position, "team": row.get("team"), "opp": row.get("opp"),
                "candidate": candidate, "proj_pts": float(value),
                "quantile_levels": model.levels.tolist(),
                "quantiles": row_quantiles.tolist(),
                "created_at_utc": created_at.astimezone(timezone.utc).isoformat(),
                "first_kickoff_utc": kickoff.isoformat(),
                "training_max_key": int((train["season"] * 100 + train["week"]).max()),
            })
    return pl.from_dicts(records, infer_schema_length=None)


def build_shadow_snapshot(root: Path, season: int, week: int, now: datetime) -> pl.DataFrame:
    """Build all three frozen candidates with independent past-only quantiles."""
    cache = root / "data/cache"
    config = load_config(root / "config.yaml")
    base = pl.read_parquet(cache / "player_weeks.parquet")
    prior_paths = [
        shadow_snapshot_path(root, season, prior_week)
        for prior_week in TEST_WEEKS if prior_week < week
        if shadow_snapshot_path(root, season, prior_week).exists()
    ]
    prior_snapshots = (
        pl.concat([pl.read_parquet(path) for path in prior_paths], how="diagonal_relaxed")
        if prior_paths else None
    )
    if prior_snapshots is not None:
        base = overlay_snapshot_points(base, prior_snapshots, "sleeper", "proj_pts")
    target = current_projection_rows(root, base, config["scoring"], season, week)
    history = base.filter(pl.col("season") * 100 + pl.col("week") < season * 100 + week)
    combined = pl.concat([history, target], how="diagonal_relaxed")

    defense_weeks = defense_attempt_history(cache)
    def_frame = add_def_stop_projection(combined, defense_weeks, config["scoring"])
    if prior_snapshots is not None:
        def_frame = overlay_snapshot_points(def_frame, prior_snapshots, "def_stop", "def_stop")
    stats = pl.read_parquet(cache / "nflverse_player_stats.parquet")
    snaps = pl.read_parquet(cache / "nflverse_snap_counts.parquet")
    mapping = pl.read_parquet(cache / "nflverse_ff_playerids.parquet")
    schedules = pl.read_parquet(cache / "nflverse_schedules.parquet")
    expanded_history, expanded_target = expanded_candidate_frames(
        combined, stats, snaps, mapping, schedules, season, week
    )
    if prior_snapshots is not None:
        expanded_history = overlay_snapshot_points(
            expanded_history, prior_snapshots, "expanded_ridge", "expanded_ridge"
        )
    kickoff = first_kickoff_utc(schedules, season, week)
    if now.astimezone(timezone.utc) >= kickoff:
        raise RuntimeError(f"shadow snapshot deadline passed: {kickoff.isoformat()}")

    sleeper_history = combined.with_columns(pl.col("proj_pts").alias("sleeper"))
    sleeper_target = target.with_columns(pl.col("proj_pts").alias("sleeper"))
    frames = [
        candidate_snapshot_rows("sleeper", sleeper_history, sleeper_target, "sleeper", now, kickoff),
        candidate_snapshot_rows("def_stop", def_frame, def_frame.filter(
            (pl.col("season") == season) & (pl.col("week") == week)
        ), "def_stop", now, kickoff),
        candidate_snapshot_rows(
            "expanded_ridge", expanded_history, expanded_target,
            "expanded_ridge", now, kickoff,
        ),
    ]
    return pl.concat(frames, how="diagonal_relaxed").sort("candidate", "pos", "sleeper_id")


def write_shadow_report(root: Path, completed: list[int], season: int) -> Path:
    """Rebuild the cumulative report from immutable completed-week snapshots."""
    actuals = pl.read_parquet(root / "data/cache/player_weeks.parquet")
    position_frames = []
    weekly_frames = []
    snapshot_rows = []
    for week in TEST_WEEKS:
        path = shadow_snapshot_path(root, season, week)
        snapshot_rows.append((week, path.exists(), week in completed))
        if path.exists() and week in completed:
            position, weekly = score_shadow_snapshot(pl.read_parquet(path), actuals)
            position_frames.append(position)
            weekly_frames.append(weekly)
    position = pl.concat(position_frames) if position_frames else None
    weekly = pl.concat(weekly_frames) if weekly_frames else None
    status = adoption_status(weekly) if weekly is not None else {
        candidate: {"weeks_scored": 0, "spearman_wins": 0, "crps": float("nan"),
                    "baseline_crps": float("nan"), "crps_guard": False,
                    "eligible": False, "decision": "pending"}
        for candidate in CANDIDATES[1:]
    }
    lines = [
        "# Shadow projection test", "",
        "- Default projection: unchanged (`sleeper`).",
        "- Frozen test weeks: 2026 weeks 7-12.",
        "- Rule: at least 4/6 weekly aggregate Spearman wins versus Sleeper and total sample-weighted CRPS no more than 0.5% worse.",
        "- Quantiles are refit separately per candidate using only rows before each snapshot week.", "",
        "## Snapshot status", "",
        "| Week | Snapshot | Week complete |",
        "|---:|---|---|",
    ]
    for week, exists, complete in snapshot_rows:
        lines.append(f"| {week} | {'saved' if exists else 'pending'} | {'yes' if complete else 'no'} |")
    lines.extend(["", "## Weekly aggregate", ""])
    if weekly is None:
        lines.append("- No completed shadow weeks yet.")
    else:
        lines.extend([
            "| Week | Candidate | N | Spearman | CRPS |",
            "|---:|---|---:|---:|---:|",
        ])
        for row in weekly.sort("week", "candidate").iter_rows(named=True):
            lines.append(
                f"| {row['week']} | {row['candidate']} | {row['n']} | "
                f"{row['spearman']:.5f} | {row['crps']:.4f} |"
            )
        lines.extend(["", "## Position metrics", "", "| Week | Pos | Candidate | N | Spearman | CRPS |", "|---:|---|---|---:|---:|---:|"])
        for row in position.sort("week", "pos", "candidate").iter_rows(named=True):
            spearman = "n/a" if np.isnan(row["spearman"]) else f"{row['spearman']:.5f}"
            lines.append(
                f"| {row['week']} | {row['pos']} | {row['candidate']} | {row['n']} | "
                f"{spearman} | {row['crps']:.4f} |"
            )
    lines.extend(["", "## Adoption status", ""])
    for candidate in CANDIDATES[1:]:
        row = status[candidate]
        crps = "n/a" if not np.isfinite(row["crps"]) else f"{row['crps']:.4f}"
        lines.append(
            f"- `{candidate}`: {row['decision']}; weeks scored {row['weeks_scored']}/6; "
            f"Spearman wins {row['spearman_wins']}/6; total CRPS {crps}; "
            f"0.5% guard {'passed' if row['crps_guard'] else 'not yet passed'}."
        )
    path = root / "reports/shadow_test.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_shadow(
    root: str | Path,
    season: int,
    completed: list[int],
    now: datetime | None = None,
) -> dict:
    """Create the next pregame snapshot and score all newly completed snapshots."""
    root = Path(root)
    now = now or datetime.now(timezone.utc)
    target_week = max(completed, default=0) + 1
    snapshot_path = shadow_snapshot_path(root, season, target_week)
    created = False
    if target_week in TEST_WEEKS:
        if snapshot_path.exists():
            created = False
        else:
            frame = build_shadow_snapshot(root, season, target_week, now)
            kickoff = datetime.fromisoformat(frame.item(0, "first_kickoff_utc"))
            created = write_snapshot_before_kickoff(
                snapshot_path, frame, kickoff, datetime.now(timezone.utc)
            )
    report = write_shadow_report(root, completed, season)
    return {
        "target_week": target_week,
        "snapshot": str(snapshot_path) if target_week in TEST_WEEKS else None,
        "created": created,
        "report": str(report),
    }


def main() -> None:
    config = load_config(ROOT / "config.yaml")
    season = int(config["sim"]["current_season"])
    schedules = pl.read_parquet(ROOT / "data/cache/nflverse_schedules.parquet")
    regular = schedules.filter((pl.col("season") == season) & (pl.col("game_type") == "REG"))
    completed = sorted(
        regular.group_by("week").agg(
            (pl.col("home_score").is_not_null().all() & pl.col("away_score").is_not_null().all()).alias("complete")
        ).filter("complete").get_column("week").to_list()
    )
    print(json.dumps(run_shadow(ROOT, season, completed), indent=2))


if __name__ == "__main__":
    main()
