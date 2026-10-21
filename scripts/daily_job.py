import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import numpy as np
import polars as pl

from ffm.config import load_config
from ffm.coverage import latest_coverage_lines, weekly_position_coverage
from ffm.distributions import QuantileModel
from ffm.lineup import greedy
from ffm.market import load_market
from ffm.season import round_robin
from ffm.sleeper import cache_players, cache_state, cache_week
from ffm.worlds import load_injury_overrides
from scripts.daily_snapshot import run_daily_snapshot

POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
LONG_TERM = {"IR", "PUP"}


def completed_weeks(schedules: pl.DataFrame, season: int) -> list[int]:
    regular = schedules.filter(
        (pl.col("season") == season) & (pl.col("game_type") == "REG")
    )
    return sorted(
        regular.group_by("week")
        .agg(
            (
                pl.col("home_score").is_not_null().all()
                & pl.col("away_score").is_not_null().all()
            ).alias("complete")
        )
        .filter("complete")
        .get_column("week")
        .to_list()
    )


def replace_season(path: Path, current: pl.DataFrame, season: int) -> None:
    if path.exists() and "season" in pl.read_parquet_schema(path):
        previous = pl.read_parquet(path).filter(pl.col("season") != season)
        current = pl.concat([previous, current], how="diagonal_relaxed")
    current.write_parquet(path)


def refresh_data(root: Path, season: int) -> dict:
    """Refresh only current-season/current-day sources needed by the daily job."""
    import nflreadpy as nfl

    cache = root / "data/cache"
    cache.mkdir(parents=True, exist_ok=True)
    state = cache_state(cache)
    cache_players(cache, force=True)
    schedules = nfl.load_schedules([season])
    injuries = nfl.load_injuries([season])
    replace_season(cache / "nflverse_schedules.parquet", schedules, season)
    replace_season(cache / "nflverse_injuries.parquet", injuries, season)
    completed = completed_weeks(schedules, season)
    new_stats = []
    for week in completed:
        path = cache / f"sleeper_stats_{season}_w{week:02d}.parquet"
        if not path.exists():
            cache_week(season, week, "stats", cache)
            new_stats.append(week)
    future = []
    for week in range(max(completed, default=0) + 1, 19):
        try:
            cache_week(season, week, "projections", cache, force=True)
            future.append(week)
        except RuntimeError:
            continue
    load_market(cache)
    if new_stats:
        subprocess.run([sys.executable, str(root / "scripts/build_dataset.py")], check=True)
    return {"state": state, "completed": completed, "new_stats": new_stats, "future": future}


def injury_snapshot(players: pl.DataFrame) -> pl.DataFrame:
    return players.select(
        pl.col("player_id").cast(pl.String), "full_name", "team", "position",
        "injury_status", "status", "active",
    ).sort("player_id")


def injury_diff(current: pl.DataFrame, previous: pl.DataFrame | None) -> pl.DataFrame:
    """Return rows whose Sleeper injury status or roster status changed."""
    if previous is None or previous.is_empty():
        return current.head(0).with_columns(
            pl.lit(None).cast(pl.String).alias("previous_injury_status"),
            pl.lit(None).cast(pl.String).alias("previous_status"),
        )
    old = previous.select(
        "player_id",
        pl.col("injury_status").alias("previous_injury_status"),
        pl.col("status").alias("previous_status"),
    )
    return (
        current.join(old, on="player_id", how="left")
        .filter(
            (
                pl.col("injury_status").fill_null("")
                != pl.col("previous_injury_status").fill_null("")
            )
            | (
                pl.col("status").fill_null("")
                != pl.col("previous_status").fill_null("")
            )
        )
    )


def status_play_probability(
    injury_status: str | None,
    sleeper_status: str | None,
    availability: dict,
    overridden_out: bool = False,
) -> float:
    """Return current-week play probability; explicit overrides always win."""
    if overridden_out:
        return 0.0
    injury_status = injury_status or "none"
    sleeper_status = sleeper_status or ""
    if injury_status in LONG_TERM or sleeper_status in {"Injured Reserve", "PUP"}:
        return 0.0
    table = availability["status_play_probability"]
    return float(table.get(injury_status, table["none"])["probability"])


def current_opponent(league: dict, my_team: int) -> int:
    for left, right in round_robin(len(league["teams"]))[0]:
        if left == my_team:
            return right
        if right == my_team:
            return left
    raise RuntimeError("current opponent not found")


def injury_sections(
    changes: pl.DataFrame,
    league: dict,
    players: pl.DataFrame,
    my_team: int,
    opponent: int,
) -> list[str]:
    id_to_index = {
        str(row["player_id"]): int(row["player_index"])
        for row in players.select("player_id", "player_index").iter_rows(named=True)
    }
    membership = {}
    for team, roster in enumerate(league["rosters"]):
        for index in roster:
            membership[index] = team
    groups = [
        ("Diego's roster", my_team),
        (f"Opponent: {league['teams'][opponent]}", opponent),
        ("Other rosters", None),
    ]
    lines = []
    for title, target in groups:
        lines.extend([f"### {title}", ""])
        selected = []
        for row in changes.iter_rows(named=True):
            index = id_to_index.get(str(row["player_id"]))
            team = membership.get(index)
            if (target is None and team not in {None, my_team, opponent}) or team == target:
                selected.append(row)
        if not selected:
            lines.append("- None.")
        else:
            for row in selected:
                before = row.get("previous_injury_status") or row.get("previous_status") or "none"
                after = row.get("injury_status") or row.get("status") or "none"
                lines.append(f"- {row['full_name']}: {before} → {after}.")
        lines.append("")
    return lines


def lineup_rows(
    players: pl.DataFrame,
    projections: np.ndarray,
    roster: list[int],
    sleeper_players: pl.DataFrame,
    model: QuantileModel,
    availability: dict,
    override_names: set[str],
) -> list[dict]:
    health = {
        str(row["player_id"]): row
        for row in sleeper_players.select(
            "player_id", "injury_status", "status"
        ).iter_rows(named=True)
    }
    probabilities = np.ones(players.height)
    for row in players.iter_rows(named=True):
        health_row = health.get(str(row["player_id"]), {})
        probabilities[row["player_index"]] = status_play_probability(
            health_row.get("injury_status"), health_row.get("status"), availability,
            str(row["name"] or "").lower() in override_names,
        )
    indices = np.asarray(roster, dtype=int)
    expected = projections[indices] * probabilities[indices]
    selected = greedy(
        expected,
        players.get_column("position").to_numpy()[indices],
        probabilities[indices] > 0,
    )
    rows = []
    for local_index in np.flatnonzero(selected):
        index = int(indices[local_index])
        row = players.row(index, named=True)
        position = row["position"]
        projection = float(projections[index])
        quantiles = model.ppf(
            position,
            np.array([projection, projection, projection]),
            np.array([0.10, 0.50, 0.90]),
        )
        rows.append({
            "name": row["name"] or row["player_id"],
            "position": position,
            "p10": float(quantiles[0]),
            "p50": float(quantiles[1]),
            "p90": float(quantiles[2]),
            "play_probability": float(probabilities[index]),
        })
    order = {position: index for index, position in enumerate(POSITIONS)}
    return sorted(rows, key=lambda row: (order[row["position"]], -row["p50"]))


def market_movers(market: pl.DataFrame, sleeper_players: pl.DataFrame, ascending: bool) -> pl.DataFrame:
    healthy = sleeper_players.select(
        pl.col("player_id").cast(pl.String).alias("sleeper_id"),
        "injury_status", "active",
    )
    return (
        market.join(healthy, on="sleeper_id", how="inner")
        .filter(
            pl.col("active")
            & (pl.col("injury_status").is_null() | (pl.col("injury_status") == ""))
        )
        .sort("trend_30_day", descending=not ascending)
        .head(10)
    )


def write_needs_review(
    path: Path,
    sleeper_players: pl.DataFrame,
    league: dict,
    players: pl.DataFrame,
    my_team: int,
    override_names: set[str],
) -> None:
    roster_ids = {
        str(players.row(index, named=True)["player_id"])
        for index in league["rosters"][my_team]
    }
    candidates = sleeper_players.filter(
        pl.col("player_id").cast(pl.String).is_in(roster_ids)
        & (
            pl.col("injury_status").is_in(sorted(LONG_TERM))
            | pl.col("status").is_in(["Injured Reserve", "PUP"])
        )
        & ~pl.col("full_name").str.to_lowercase().is_in(sorted(override_names))
    )
    lines = ["# Injury overrides needing review", ""]
    if candidates.is_empty():
        lines.append("- None.")
    else:
        lines.append("Proposed entries; review before copying to `overrides.yaml`.")
        lines.append("")
        lines.append("```yaml")
        lines.append("overrides:")
        for row in candidates.iter_rows(named=True):
            lines.extend([
                f"  - name: {row['full_name']}",
                "    status: out",
                "    weeks: TBD",
                f"    note: Sleeper {row['injury_status'] or row['status']}",
            ])
        lines.append("```")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_daily(root: Path, dry_run: bool = False, now: datetime | None = None) -> Path:
    started = time.perf_counter()
    now = now or datetime.now(timezone.utc)
    local_date = now.astimezone(ZoneInfo("America/Chicago")).date().isoformat()
    config = load_config(root / "config.yaml")
    season = int(config["sim"]["current_season"])
    refresh = {"completed": [], "new_stats": [], "future": [], "state": {}}
    if not dry_run:
        refresh = refresh_data(root, season)

    cache = root / "data/cache"
    sleeper_players = pl.read_parquet(cache / "sleeper_players.parquet")
    schedules = pl.read_parquet(cache / "nflverse_schedules.parquet")
    completed = completed_weeks(schedules, season)
    snapshots = root / "data/injury_snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    current_snapshot = injury_snapshot(sleeper_players)
    prior_paths = sorted(path for path in snapshots.glob("*.parquet") if path.stem < local_date)
    previous = pl.read_parquet(prior_paths[-1]) if prior_paths else None
    changes = injury_diff(current_snapshot, previous)
    current_snapshot.write_parquet(snapshots / f"{local_date}.parquet")

    manifest = json.loads((root / "models/world_manifest.json").read_text(encoding="utf-8"))
    world_dir = Path(manifest["world_dir"])
    players = pl.read_parquet(world_dir / "player_index.parquet")
    projections = np.load(world_dir / "proj_seen.npy", mmap_mode="r")[0].mean(axis=0)
    league = json.loads((root / "models/synthetic_league.json").read_text(encoding="utf-8"))
    my_team = league["teams"].index(config["league"]["my_team"])
    opponent = current_opponent(league, my_team)
    availability = json.loads((root / "models/availability.json").read_text(encoding="utf-8"))
    overrides = load_injury_overrides(root / "overrides.yaml")
    override_names = {
        str(row.get("name", "")).lower()
        for row in overrides
        if str(row.get("status", "")).lower() in {"out", "out_for_season", "ir"}
    }
    quantile_model = QuantileModel.load(root / "models/quantiles_2026.npz")
    starters = lineup_rows(
        players, projections, league["rosters"][my_team], sleeper_players,
        quantile_model, availability, override_names,
    )
    market = load_market(cache, now.astimezone(ZoneInfo("America/Chicago")))
    fallers = market_movers(market, sleeper_players, ascending=True)
    risers = market_movers(market, sleeper_players, ascending=False)
    coverage = weekly_position_coverage(
        pl.read_parquet(cache / "player_weeks.parquet"), quantile_model, season
    )
    if int(manifest["first_week"]) in completed:
        snapshot_note = "Forward snapshot deferred until P6 worlds are rebuilt."
    else:
        run_daily_snapshot(root, now)
        snapshot_note = "Forward snapshot saved."
    write_needs_review(
        root / "reports/injuries/needs_review.md", sleeper_players, league,
        players, my_team, override_names,
    )

    lines = [
        f"# Daily fantasy report: {local_date}", "",
        f"- Mode: {'cached dry-run' if dry_run else 'live refresh'}",
        f"- Current model week: {manifest['first_week']}",
        f"- Completed regular-season weeks: {', '.join(map(str, completed)) or 'none'}",
        f"- Newly cached Sleeper stats: {', '.join(map(str, refresh['new_stats'])) or 'none'}",
        f"- {snapshot_note}",
        "", "## Injury changes", "",
        *injury_sections(changes, league, players, my_team, opponent),
        "## Start/sit", "",
        f"Opponent: {league['teams'][opponent]}", "",
        "| Starter | Pos | P10 | P50 | P90 | Play probability |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in starters:
        lines.append(
            f"| {row['name']} | {row['position']} | {row['p10']:.2f} | "
            f"{row['p50']:.2f} | {row['p90']:.2f} | {row['play_probability']:.1%} |"
        )
    lines.extend(["", "## Healthy market fallers", ""])
    for row in fallers.iter_rows(named=True):
        lines.append(
            f"- {row['market_name']} ({row['market_position']}): "
            f"V={row['market_value']:.0f}, 30-day={row['trend_30_day']:+.0f}."
        )
    if fallers.is_empty():
        lines.append("- None.")
    lines.extend(["", "## Healthy market risers", ""])
    for row in risers.iter_rows(named=True):
        lines.append(
            f"- {row['market_name']} ({row['market_position']}): "
            f"V={row['market_value']:.0f}, 30-day={row['trend_30_day']:+.0f}."
        )
    if risers.is_empty():
        lines.append("- None.")
    lines.extend(["", "## Weekly interval coverage", "", *latest_coverage_lines(coverage)])
    runtime = time.perf_counter() - started
    lines.extend(["", f"Runtime: {runtime:.3f} seconds."])
    report = "\n".join(lines) + "\n"
    dated = root / "reports/daily" / f"daily_{local_date}.md"
    dated.parent.mkdir(parents=True, exist_ok=True)
    dated.write_text(report, encoding="utf-8")
    latest = root / "reports/daily_latest.md"
    latest.write_text(report, encoding="utf-8")
    return latest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(run_daily(ROOT, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
