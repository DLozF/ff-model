import json
from pathlib import Path

import nflreadpy as nfl
import polars as pl

from ffm.actuals import nflverse_actual_rows, projection_team_gaps, replace_season
from ffm.config import load_config
from build_dataset import load_projections, load_stats

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"


def validation_table(nfl_actuals: pl.DataFrame, sleeper_actuals: pl.DataFrame):
    """Compare scoring.py output from nflverse with Sleeper actual PPR points."""
    sleeper = sleeper_actuals.filter(
        (pl.col("season") == 2026)
        & pl.col("week").is_between(1, 5)
        & pl.col("pts_ppr").is_not_null()
    ).select(
        "season", "week", "player_id", pl.col("pts_ppr").alias("sleeper_points")
    )
    compared = (
        nfl_actuals.filter(pl.col("week").is_between(1, 5))
        .select("season", "week", "player_id", pl.col("pts_ppr").alias("nflverse_points"))
        .join(sleeper, on=["season", "week", "player_id"], how="inner")
        .with_columns(
            (pl.col("nflverse_points") - pl.col("sleeper_points")).abs().alias("difference")
        )
    )
    summary = compared.select(
        pl.len().alias("n"),
        (pl.col("difference") <= 0.5).sum().alias("matched"),
        (pl.col("difference") <= 0.5).mean().alias("rate"),
    ).row(0, named=True)
    return compared, summary


def write_audit(summary, week6_rows, gaps, accepted):
    lines = [
        "# Actual-stat audit", "",
        "## nflverse validation against Sleeper, 2026 weeks 1-5", "",
        f"- Compared rows: {summary['n']}",
        f"- Within 0.5 points: {summary['matched']}",
        f"- Match rate: {summary['rate']:.6%}",
        f"- Required threshold: 95% — {'PASS' if accepted else 'FAIL'}", "",
        "## 2026 week 6", "",
        f"- nflverse scored actual rows cached: {week6_rows if accepted else 0}",
        f"- Week 6 treatment: {'included from nflverse' if accepted else 'excluded from all tests/training'}", "",
        "## Completed-week projection teams with no actual-stat rows", "",
        f"- Team-week gaps found: {gaps.height}",
        f"- Gaps for teams with a scheduled game: {gaps.filter(pl.col('scheduled_game')).height}",
        f"- Bye-week-only gaps: {gaps.filter(~pl.col('scheduled_game')).height}", "",
        "| Season | Week | Team | Projection rows | Actual rows | Scheduled game |",
        "|---:|---:|---|---:|---:|---|",
    ]
    for row in gaps.iter_rows(named=True):
        lines.append(
            f"| {row['season']} | {row['week']} | {row['team']} | "
            f"{row['projection_rows']} | {row['actual_rows']} | "
            f"{'yes' if row['scheduled_game'] else 'no (bye)'} |"
        )
    if gaps.is_empty():
        lines.append("| - | - | None | - | - | - |")
    (ROOT / "reports/actuals_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ROOT / "logs/projection-actual-team-gaps.json").write_text(
        json.dumps(gaps.to_dicts(), indent=2), encoding="utf-8"
    )


def main():
    scoring = load_config()["scoring"]
    fresh_2026 = nfl.load_player_stats([2026], summary_level="week")
    existing = pl.read_parquet(CACHE / "nflverse_player_stats.parquet")
    refreshed = replace_season(existing, fresh_2026, 2026)
    refreshed.write_parquet(CACHE / "nflverse_player_stats.parquet")

    fresh_schedules = nfl.load_schedules([2026])
    existing_schedules = pl.read_parquet(CACHE / "nflverse_schedules.parquet")
    schedules = replace_season(existing_schedules, fresh_schedules, 2026)
    schedules.write_parquet(CACHE / "nflverse_schedules.parquet")

    ids = pl.read_parquet(CACHE / "nflverse_ff_playerids.parquet")
    nfl_actuals = nflverse_actual_rows(fresh_2026, ids, scoring)
    sleeper_actuals = load_stats().filter(pl.col("season") == 2026)
    compared, summary = validation_table(nfl_actuals, sleeper_actuals)
    accepted = summary["rate"] >= 0.95
    supplement = CACHE / "nflverse_actuals_2026_w06.parquet"
    if accepted:
        week6 = nfl_actuals.filter(pl.col("week") == 6)
        week6.write_parquet(supplement)
    else:
        week6 = nfl_actuals.head(0)
        supplement.unlink(missing_ok=True)

    all_actuals = load_stats()
    projections = load_projections()
    gaps = projection_team_gaps(projections, all_actuals, schedules)
    write_audit(summary, week6.height, gaps, accepted)
    compared.sort("difference", descending=True).head(20).write_parquet(
        CACHE / "nflverse_validation_largest.parquet"
    )
    print(f"validation: {summary['matched']}/{summary['n']} = {summary['rate']:.6f}")
    print(f"week6 accepted: {accepted}; rows: {week6.height}")
    print(f"completed team gaps: {gaps.height}")
    for row in gaps.iter_rows(named=True):
        print(row)


if __name__ == "__main__":
    main()
