import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import polars as pl
import yaml

from ffm.yahoo_loader import load_yahoo_tables
from ffm.yahoo_paste import (
    match_roster,
    normalize_player_name,
    parse_available_text,
    parse_roster_page,
    parse_roster_text,
    parse_schedule_text,
    parse_settings_text,
    parse_standings_text,
)

ROOT = Path("/opt/data/ff-model")
PASTE = ROOT / "data/yahoo_paste"
CACHE = ROOT / "data/cache"


class FullPasteError(RuntimeError):
    def __init__(self, needs_diego: list[str]):
        super().__init__("full Yahoo paste import is incomplete")
        self.needs_diego = needs_diego


def _partial_import() -> None:
    parsed = parse_settings_text((PASTE / "settings.txt").read_text(encoding="utf-8"))
    roster_text = (PASTE / "my_roster.txt").read_text(encoding="utf-8")
    roster = parse_roster_text(roster_text)
    players = pl.read_parquet(CACHE / "sleeper_players.parquet")
    matched, unmatched = match_roster(roster, players)
    team_name = (PASTE / "my_team.txt").read_text(encoding="utf-8").strip()

    waiver_match = re.search(r"Waiver priority:\s*(\d+)", roster_text)
    week_match = re.search(r"current week\s+(\d+)", roster_text, re.IGNORECASE)
    parsed["league"].update({
        "my_team": team_name,
        "regular_season_weeks": [1, parsed["league"]["playoff_weeks"][0] - 1],
        "waiver_priority": int(waiver_match.group(1)) if waiver_match else None,
        "current_week": int(week_match.group(1)) if week_match else None,
        "faab_budget": None,
        "partial_import": True,
        "acquisition_limit": None,
        "weekly_acquisition_limit": None,
    })

    config_path = ROOT / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    old = json.loads(json.dumps(config))
    config["league"].update(parsed["league"])
    config["scoring"].update(parsed["scoring"])
    config["idp_scoring"] = parsed["idp_scoring"]
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    CACHE.mkdir(parents=True, exist_ok=True)
    matched.write_parquet(CACHE / "yahoo_partial_roster.parquet")
    (CACHE / "yahoo_partial_settings.json").write_text(
        json.dumps({**parsed, "team_name": team_name, "old_config": old}, indent=2),
        encoding="utf-8",
    )
    available = PASTE / "available.txt"
    metadata = {
        "available_source": "pasted" if available.exists() else "estimated",
        "available_pasted_date": None,
    }
    (CACHE / "yahoo_partial_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    lines = [f"{row['slot']}\t{row['name']}\t{row['pos']}\t{row['nfl_team']}" for row in unmatched.iter_rows(named=True)]
    (ROOT / "logs/yahoo_name_unmatched.log").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    print(f"team: {team_name}")
    print(f"roster rows: {matched.height}")
    print(f"model players matched: {matched.filter(pl.col('sleeper_id').is_not_null()).height}")
    print(f"IDP rows excluded from model: {matched.filter(pl.col('model_excluded')).height}")
    print(f"unmatched model players: {unmatched.height}")
    print(f"free-agent source: {metadata['available_source']}")


def _raw_or_csv_roster(path: Path, fallback_team: str | None) -> tuple[str | None, pl.DataFrame, list[str]]:
    text = path.read_text(encoding="utf-8")
    data_lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    if data_lines and data_lines[0].lower().startswith("slot,"):
        return fallback_team, parse_roster_text(text), []
    team_name, roster, unparsed = parse_roster_page(text)
    return team_name or fallback_team, roster, unparsed


def _match_available(available: pl.DataFrame, players: pl.DataFrame) -> tuple[pl.DataFrame, list[str]]:
    if available.is_empty():
        return pl.DataFrame({"sleeper_id": []}, schema={"sleeper_id": pl.String}), []
    roster = available.with_columns(pl.lit("BN").alias("slot"))
    matched, unmatched = match_roster(roster, players)
    lines = [
        f"UNMATCHED available: {row['name']} {row['nfl_team']} - {row['pos']}"
        for row in unmatched.iter_rows(named=True)
    ]
    return matched.select(pl.col("sleeper_id").cast(pl.String)).drop_nulls().unique(), lines


def build_full_paste_tables(directory: Path, players: pl.DataFrame, expected_teams: int = 12) -> tuple[dict, list[str], list[str]]:
    """Parse every full-league paste before allowing any persistent write."""
    required = [directory / "settings.txt", directory / "my_team.txt", directory / "my_roster.txt", directory / "standings.txt"]
    missing = [path.name for path in required if not path.exists()]
    schedule_paths = sorted(directory.glob("schedule_w*.txt"))
    if not list(directory.glob("team_*.txt")):
        missing.append("team_01.txt to team_12.txt roster pages")
    if not schedule_paths:
        missing.append("schedule_wNN.txt")
    if missing:
        raise FullPasteError([f"Paste missing file: {name}" for name in missing])

    settings = parse_settings_text((directory / "settings.txt").read_text(encoding="utf-8"))
    my_team = (directory / "my_team.txt").read_text(encoding="utf-8").strip()
    standings, team_ids, standings_unparsed = parse_standings_text(
        (directory / "standings.txt").read_text(encoding="utf-8")
    )
    if standings.height != expected_teams:
        raise FullPasteError([f"Standings parsed {standings.height}/{expected_teams} teams."])

    roster_sources = [(directory / "my_roster.txt", my_team)]
    roster_sources.extend((path, None) for path in sorted(directory.glob("team_*.txt")))
    rosters_by_team: dict[str, pl.DataFrame] = {}
    unparsed = [f"standings.txt\t{line}" for line in standings_unparsed]
    for path, fallback in roster_sources:
        team_name, roster, lines = _raw_or_csv_roster(path, fallback)
        unparsed.extend(f"{path.name}\t{line}" for line in lines)
        if not team_name:
            unparsed.append(f"{path.name}\tMISSING TEAM NAME")
            continue
        key = normalize_player_name(team_name)
        if key not in team_ids:
            unparsed.append(f"{path.name}\tUNMATCHED TEAM {team_name}")
            continue
        rosters_by_team[key] = roster
    missing_teams = [
        row["team_name"] for row in standings.iter_rows(named=True)
        if normalize_player_name(row["team_name"]) not in rosters_by_team
    ]
    if missing_teams:
        raise FullPasteError([f"Paste roster page for: {name}" for name in missing_teams])

    roster_frames = []
    unmatched_lines = []
    for key, team_id in team_ids.items():
        matched, unmatched = match_roster(rosters_by_team[key], players)
        roster_frames.append(matched.with_columns(pl.lit(team_id).alias("team_id")))
        unmatched_lines.extend(
            f"UNMATCHED player: {row['name']} {row['nfl_team']} - {row['pos']}"
            for row in unmatched.iter_rows(named=True)
        )
    if len(unmatched_lines) > 3:
        raise FullPasteError([*unparsed, *unmatched_lines])
    rosters = pl.concat(roster_frames, how="diagonal_relaxed").select(
        "team_id", pl.col("sleeper_id").cast(pl.String), "slot", "name", "pos", "nfl_team", "model_excluded"
    )

    schedule_frames = []
    for path in schedule_paths:
        text = path.read_text(encoding="utf-8")
        if not re.search(r"^Week\s+\d+", text, re.MULTILINE | re.IGNORECASE):
            week_match = re.search(r"schedule_w(\d+)", path.stem, re.IGNORECASE)
            text = f"Week {int(week_match.group(1))}\n{text}" if week_match else text
        schedule, lines = parse_schedule_text(text, team_ids)
        schedule_frames.append(schedule)
        unparsed.extend(f"{path.name}\t{line}" for line in lines)
    schedule = pl.concat(schedule_frames).unique().sort("week", "team1_id")
    if schedule.is_empty():
        raise FullPasteError(["No schedule matchups parsed."])

    rostered = set(rosters.get_column("sleeper_id").drop_nulls().to_list())
    available_path = directory / "available.txt"
    if available_path.exists():
        available, lines = parse_available_text(available_path.read_text(encoding="utf-8"))
        unparsed.extend(f"available.txt\t{line}" for line in lines)
        free_agents, available_unmatched = _match_available(available, players)
        unmatched_lines.extend(available_unmatched)
    else:
        free_agents = players.filter(
            pl.col("position").is_in(["QB", "RB", "WR", "TE", "K", "DEF"])
            & ~pl.col("player_id").cast(pl.String).is_in(rostered)
        ).select(pl.col("player_id").cast(pl.String).alias("sleeper_id"))

    league_settings = {
        **settings["league"],
        "my_team": my_team,
        "regular_season_weeks": [1, settings["league"]["playoff_weeks"][0] - 1],
        "partial_import": False,
        "scoring": settings["scoring"],
    }
    tables = {
        "settings": league_settings,
        "teams": standings.select("team_id", "team_name"),
        "rosters": rosters,
        "free_agents": free_agents,
        "standings": standings.drop("team_name"),
        "schedule": schedule,
    }
    return tables, unparsed, unmatched_lines


def _rebuild_real_league() -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, str(ROOT / "scripts/run_synthetic.py")], check=True, cwd=ROOT, env=env)
    subprocess.run([sys.executable, str(ROOT / "scripts/find_moves.py")], check=True, cwd=ROOT, env=env)
    subprocess.run([sys.executable, str(ROOT / "scripts/waivers_job.py")], check=True, cwd=ROOT, env=env)


def _full_import(rebuild: bool) -> None:
    players = pl.read_parquet(CACHE / "sleeper_players.parquet")
    log_path = ROOT / "logs/yahoo_paste_unparsed.log"
    try:
        tables, unparsed, unmatched = build_full_paste_tables(PASTE, players)
    except FullPasteError as exc:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("\n".join(exc.needs_diego) + "\n", encoding="utf-8")
        print("Needs Diego:")
        for line in exc.needs_diego:
            print(f"- {line}")
        raise SystemExit(2) from exc
    log_lines = [*(f"UNPARSED\t{line}" for line in unparsed), *unmatched]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + ("\n" if log_lines else ""), encoding="utf-8")
    backup = load_yahoo_tables(
        tables, ROOT / "config.yaml", CACHE, ROOT / "reports/yahoo_load_diff.md"
    )
    print(f"full Yahoo paste imported; backup: {backup.name}")
    print(f"teams: {tables['teams'].height}; roster teams: {tables['rosters']['team_id'].n_unique()}")
    print(f"schedule matchups: {tables['schedule'].height}; unmatched players: {len(unmatched)}")
    if rebuild:
        _rebuild_real_league()


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--partial", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--no-rebuild", action="store_true")
    args = parser.parse_args()
    if args.partial:
        _partial_import()
    else:
        _full_import(rebuild=not args.no_rebuild)


if __name__ == "__main__":
    main()
