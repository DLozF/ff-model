import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import polars as pl

from ffm.config import load_config
from ffm.market import load_market


def create_daily_snapshot(
    players: pl.DataFrame,
    market: pl.DataFrame,
    snapshot_dir: str | Path,
    captured_at: datetime,
    season: int,
    target_week: int,
) -> Path:
    """Write one timestamped model-versus-market forward snapshot."""
    snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = captured_at.astimezone(timezone.utc)
    local_date = captured_at.astimezone(ZoneInfo("America/Chicago")).date().isoformat()
    existing = sorted(snapshot_dir.glob(f"model_vs_market_{local_date}_*.parquet"))
    if existing:
        return existing[0]
    path = snapshot_dir / f"model_vs_market_{local_date}_{timestamp:%H%M%SZ}.parquet"
    model = players.select(
        pl.col("player_id").cast(pl.String).alias("sleeper_id"),
        "name",
        "position",
        pl.col("ros_points").cast(pl.Float64),
    ).with_columns(
        pl.col("ros_points").rank("ordinal", descending=True).over("position").alias("model_rank")
    )
    snapshot = (
        model.join(
            market.select(
                pl.col("sleeper_id").cast(pl.String),
                pl.col("market_value").cast(pl.Float64),
                pl.col("market_position_rank").cast(pl.Int64),
            ),
            on="sleeper_id",
            how="inner",
        )
        .with_columns(
            pl.lit(timestamp).alias("captured_at"),
            pl.lit(season).cast(pl.Int64).alias("season"),
            pl.lit(target_week).cast(pl.Int64).alias("target_week"),
            pl.lit(None).cast(pl.Float64).alias("actual_points"),
        )
        .select(
            "captured_at", "season", "target_week", "sleeper_id", "name", "position",
            "ros_points", "model_rank", "market_value", "market_position_rank", "actual_points",
        )
    )
    snapshot.write_parquet(path)
    return path


def finalize_snapshot(path: str | Path, actuals: pl.DataFrame) -> pl.DataFrame:
    """Attach target-week actuals and summarize rank accuracy by position."""
    path = Path(path)
    snapshot = pl.read_parquet(path)
    season = int(snapshot.get_column("season")[0])
    week = int(snapshot.get_column("target_week")[0])
    week_actuals = (
        actuals.filter((pl.col("season") == season) & (pl.col("week") == week))
        .select(
            pl.col("sleeper_id").cast(pl.String),
            pl.col("act_pts").cast(pl.Float64).alias("new_actual_points"),
        )
        .unique("sleeper_id", keep="last")
    )
    if week_actuals.is_empty():
        return pl.DataFrame()
    finalized = (
        snapshot.drop([column for column in ("actual_rank", "model_rank_error", "market_rank_error") if column in snapshot.columns])
        .join(week_actuals, on="sleeper_id", how="left")
        .with_columns(
            pl.coalesce("new_actual_points", pl.lit(0.0)).alias("actual_points")
        )
        .drop("new_actual_points")
        .with_columns(
            pl.col("actual_points").rank("average", descending=True).over("position").alias("actual_rank")
        )
        .with_columns(
            (pl.col("model_rank") - pl.col("actual_rank")).abs().alias("model_rank_error"),
            (pl.col("market_position_rank") - pl.col("actual_rank")).abs().alias("market_rank_error"),
        )
    )
    finalized.write_parquet(path)
    return (
        finalized.group_by("captured_at", "season", "target_week", "position")
        .agg(
            pl.len().alias("players"),
            pl.col("model_rank_error").mean().alias("model_mae"),
            pl.col("market_rank_error").mean().alias("market_mae"),
        )
        .with_columns(
            pl.when(pl.col("model_mae") < pl.col("market_mae"))
            .then(pl.lit("model"))
            .when(pl.col("market_mae") < pl.col("model_mae"))
            .then(pl.lit("market"))
            .otherwise(pl.lit("tie"))
            .alias("closer")
        )
        .rename({"target_week": "week"})
        .select(
            "captured_at", "season", "week", "position", "players",
            "model_mae", "market_mae", "closer",
        )
        .sort("position")
    )


REPORT_START = "<!-- forward-test:start -->"
REPORT_END = "<!-- forward-test:end -->"


def update_forward_report(path: str | Path, comparisons: pl.DataFrame) -> None:
    """Upsert the generated forward-test section without disturbing rank-gap content."""
    path = Path(path)
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Model vs market\n"
    if REPORT_START in existing and REPORT_END in existing:
        before, remainder = existing.split(REPORT_START, 1)
        _, after = remainder.split(REPORT_END, 1)
        existing = before.rstrip() + after
    lines = [
        REPORT_START,
        "## Forward-test rank accuracy",
        "",
        "Mean absolute error versus each week's actual within-position rank; lower is better.",
        "",
        "| Snapshot | Season | Week | Pos | Players | Model MAE | Market MAE | Closer |",
        "|---|---:|---:|---|---:|---:|---:|---|",
    ]
    if comparisons.is_empty():
        lines.append("| - | - | - | - | - | - | - | No completed snapshots yet |")
    else:
        for row in comparisons.sort("captured_at", "position").iter_rows(named=True):
            captured = row["captured_at"].astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            lines.append(
                f"| {captured} | {row['season']} | {row['week']} | {row['position']} | "
                f"{row['players']} | {row['model_mae']:.3f} | {row['market_mae']:.3f} | "
                f"{row['closer']} |"
            )
    lines.append(REPORT_END)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(existing.rstrip() + "\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def completed_regular_weeks(schedules: pl.DataFrame, season: int) -> set[int]:
    """Return regular-season weeks whose games all have final scores."""
    return set(
        schedules.filter((pl.col("season") == season) & (pl.col("game_type") == "REG"))
        .group_by("week")
        .agg(
            (pl.col("home_score").is_not_null().all() & pl.col("away_score").is_not_null().all())
            .alias("complete")
        )
        .filter("complete")
        .get_column("week")
        .cast(pl.Int64)
        .to_list()
    )


def run_daily_snapshot(root: str | Path, now: datetime | None = None) -> Path:
    """Finalize completed forecasts, update the report, and save today's forecast."""
    root = Path(root)
    captured_at = now or datetime.now(timezone.utc)
    if captured_at.tzinfo is None:
        captured_at = captured_at.replace(tzinfo=timezone.utc)
    config = load_config(root / "config.yaml")
    season = int(config["sim"]["current_season"])
    cache = root / "data/cache"
    snapshots = root / "data/snapshots"
    schedules = pl.read_parquet(cache / "nflverse_schedules.parquet")
    actuals = pl.read_parquet(cache / "player_weeks.parquet")
    completed = completed_regular_weeks(schedules, season)

    comparisons = []
    for path in sorted(snapshots.glob("model_vs_market_*.parquet")):
        snapshot = pl.read_parquet(path, columns=["season", "target_week"])
        snapshot_season = int(snapshot.get_column("season")[0])
        target_week = int(snapshot.get_column("target_week")[0])
        if snapshot_season == season and target_week in completed:
            comparison = finalize_snapshot(path, actuals)
            if not comparison.is_empty():
                comparisons.append(comparison)
    combined = pl.concat(comparisons) if comparisons else pl.DataFrame()
    update_forward_report(root / "reports/model_vs_market.md", combined)

    manifest = json.loads((root / "models/world_manifest.json").read_text(encoding="utf-8"))
    target_week = int(manifest["first_week"])
    if target_week in completed:
        raise RuntimeError(
            f"active model starts in completed week {target_week}; regenerate worlds before snapshotting"
        )
    players = pl.read_parquet(Path(manifest["world_dir"]) / "player_index.parquet")
    market = load_market(cache, captured_at.astimezone(ZoneInfo("America/Chicago")))
    return create_daily_snapshot(
        players, market, snapshots, captured_at, season=season, target_week=target_week
    )


def main() -> None:
    path = run_daily_snapshot(ROOT)
    print(path)


if __name__ == "__main__":
    main()
