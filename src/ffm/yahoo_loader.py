import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import polars as pl
import yaml
from dotenv import load_dotenv

from ffm.ids import normalize_team

POSITION_MAP = {"W/R/T": "FLEX", "W/R": "FLEX", "D/ST": "DEF"}
STAT_MAP = {
    "passing yards": "pass_yd", "passing touchdowns": "pass_td",
    "interceptions": "pass_int", "passing 2-point conversions": "pass_2pt",
    "rushing yards": "rush_yd", "rushing touchdowns": "rush_td",
    "rushing 2-point conversions": "rush_2pt", "receptions": "rec",
    "receiving yards": "rec_yd", "receiving touchdowns": "rec_td",
    "receiving 2-point conversions": "rec_2pt", "fumbles lost": "fum_lost",
    "return touchdowns": "ret_td", "extra points made": "xpm",
    "sacks": "def_sack", "defensive interceptions": "def_int",
    "fumble recoveries": "def_fum_rec", "defensive touchdowns": "def_td",
    "safeties": "def_safety", "blocked kicks": "def_blk_kick",
}


class YahooTableError(ValueError):
    """Identify the Yahoo table that could not be parsed or validated."""

    def __init__(self, table: str, message: str):
        self.table = table
        super().__init__(f"{table}: {message}")


def _table(name: str, rows, required=()) -> pl.DataFrame:
    try:
        frame = pl.from_dicts(rows, infer_schema_length=None)
    except Exception as exc:
        raise YahooTableError(name, str(exc)) from exc
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise YahooTableError(name, f"missing columns {missing}")
    return frame


def _id_map(ids: pl.DataFrame) -> dict[str, str]:
    if ids.is_empty():
        return {}
    return {
        str(int(row["yahoo_id"])): str(row["sleeper_id"])
        for row in ids.select("yahoo_id", "sleeper_id").drop_nulls().iter_rows(named=True)
    }


def _player_record(player: dict, mapping: dict[str, str]) -> dict:
    yahoo_id = str(player.get("player_id"))
    position = POSITION_MAP.get(player.get("primary_position"), player.get("primary_position"))
    team = normalize_team(player.get("editorial_team_abbr"))
    name = player.get("name", {})
    full_name = name.get("full") if isinstance(name, dict) else str(name)
    sleeper_id = team if position == "DEF" else mapping.get(yahoo_id)
    return {
        "yahoo_id": yahoo_id, "sleeper_id": sleeper_id, "name": full_name,
        "pos": position, "team": team,
    }


def _scoring(settings: dict) -> dict:
    categories = {
        int(row["stat_id"]): row for row in settings.get("stat_categories", [])
    }
    result = {}
    defense_tiers = {}
    for modifier in settings.get("stat_modifiers", []):
        category = categories.get(int(modifier["stat_id"]), {})
        name = re.sub(r"\s+", " ", category.get("name", "").lower()).strip()
        key = STAT_MAP.get(name)
        if key:
            result[key] = float(modifier["value"])
            continue
        if "field goals" in name:
            if "0-19" in name:
                result["fgm_0_19"] = float(modifier["value"])
            elif "20-29" in name:
                result["fgm_20_29"] = float(modifier["value"])
            elif "30-39" in name:
                result["fgm_30_39"] = float(modifier["value"])
            elif "40-49" in name:
                result["fgm_40_49"] = float(modifier["value"])
            elif "50" in name:
                result["fgm_50p"] = float(modifier["value"])
        if "points allowed" in name:
            for tier in ("0", "1-6", "7-13", "14-20", "21-27", "28-34", "35+"):
                if tier in name:
                    defense_tiers[tier] = float(modifier["value"])
    if defense_tiers:
        result["def_pts_allowed"] = defense_tiers
    return result


def parse_yahoo_payload(payload: dict, ids: pl.DataFrame) -> dict:
    """Normalize saved Yahoo JSON into model-ready tables."""
    try:
        league = payload["league"]
        raw_settings = payload["settings"]
    except Exception as exc:
        raise YahooTableError("settings", str(exc)) from exc
    lineup = {}
    bench = 0
    for row in raw_settings.get("roster_positions", []):
        position = POSITION_MAP.get(row["position"], row["position"])
        if position in {"BN", "IR", "IR+"}:
            if position == "BN":
                bench += int(row["count"])
        elif row.get("is_starting_position", 1):
            lineup[position] = lineup.get(position, 0) + int(row["count"])
    playoff_start = int(raw_settings["playoff_start_week"])
    settings = {
        "teams": int(league["num_teams"]), "current_week": int(league["current_week"]),
        "lineup": lineup, "bench": bench,
        "regular_season_weeks": [int(league["start_week"]), playoff_start - 1],
        "playoff_teams": int(raw_settings["num_playoff_teams"]),
        "playoff_weeks": list(range(playoff_start, int(league["end_week"]) + 1)),
        "scoring": _scoring(raw_settings),
    }
    mapping = _id_map(ids)
    roster_rows = []
    team_rows = []
    try:
        for team in payload["teams"]:
            team_rows.append({"team_id": int(team["team_id"]), "team_name": team["name"]})
            for player in team.get("roster", []):
                roster_rows.append({
                    "team_id": int(team["team_id"]), "team_name": team["name"],
                    **_player_record(player, mapping),
                })
    except Exception as exc:
        raise YahooTableError("rosters", str(exc)) from exc
    try:
        free_agents = [
            _player_record(player, mapping) for player in payload.get("free_agents", [])
        ]
    except Exception as exc:
        raise YahooTableError("free_agents", str(exc)) from exc
    return {
        "settings": settings,
        "teams": _table("teams", team_rows, ("team_id", "team_name")),
        "rosters": _table("rosters", roster_rows, ("team_id", "sleeper_id")),
        "free_agents": _table("free_agents", free_agents),
        "standings": _table(
            "standings", payload.get("standings", []),
            ("team_id", "wins", "losses", "points_for", "rank"),
        ),
        "schedule": _table(
            "schedule", payload.get("schedule", []),
            ("week", "team1_id", "team2_id"),
        ),
    }


def fetch_yahoo_payload(env_path: Path) -> dict:
    """Authenticate with yfpy and fetch the current league."""
    from yfpy.query import YahooFantasySportsQuery

    load_dotenv(env_path)
    query = YahooFantasySportsQuery(
        league_id=os.environ["YAHOO_LEAGUE_ID"], game_code="nfl",
        yahoo_consumer_key=os.environ["YAHOO_CLIENT_ID"],
        yahoo_consumer_secret=os.environ["YAHOO_CLIENT_SECRET"],
        env_file_location=env_path, save_token_data_to_env_file=True,
        browser_callback=False,
    )
    info = query.get_league_info()
    settings = query.get_league_settings()
    teams = query.get_league_teams()
    team_rows = []
    for team in teams:
        roster = query.get_team_roster_player_info_by_week(team.team_id, info.current_week)
        team_rows.append({
            "team_id": team.team_id, "name": team.name.decode("utf-8"),
            "roster": [player.serialized() for player in roster],
        })
    all_players = query.get_league_players()
    free_agents = [
        player.serialized() for player in all_players
        if getattr(player.ownership, "ownership_type", "") in {"freeagents", "waivers", "free agent"}
    ]
    standings = [
        {"team_id": team.team_id, "wins": team.wins, "losses": team.losses,
         "ties": team.ties, "points_for": team.points_for, "rank": team.rank}
        for team in query.get_league_standings().teams
    ]
    schedule = []
    for week in range(int(info.start_week), int(info.end_week) + 1):
        for matchup in query.get_league_matchups_by_week(week):
            if len(matchup.teams) == 2:
                schedule.append({"week": week, "team1_id": matchup.teams[0].team_id, "team2_id": matchup.teams[1].team_id})
    return {
        "league": info.serialized(), "settings": settings.serialized(),
        "teams": team_rows, "free_agents": free_agents,
        "standings": standings, "schedule": schedule,
    }


def load_csv_tables(directory: Path) -> dict:
    """Load the documented CSV alternative into the same table structure."""
    def read(name: str) -> pl.DataFrame:
        try:
            return pl.read_csv(directory / f"{name}.csv")
        except Exception as exc:
            raise YahooTableError(name, str(exc)) from exc

    league = read("league").row(0, named=True)
    lineup = {
        row["position"]: int(row["count"])
        for row in read("lineup").iter_rows(named=True)
    }
    scoring = {
        row["config_key"]: float(row["value"])
        for row in read("scoring").iter_rows(named=True)
    }
    settings = {**league, "lineup": lineup, "scoring": scoring}
    return {
        "settings": settings,
        "teams": read("teams"),
        "rosters": read("rosters"),
        "free_agents": read("free_agents"),
        "standings": read("standings"),
        "schedule": read("schedule"),
    }


def save_tables(tables: dict, cache: Path) -> None:
    """Save normalized Yahoo tables as Parquet."""
    cache.mkdir(parents=True, exist_ok=True)
    for name in ("teams", "rosters", "free_agents", "standings", "schedule"):
        tables[name].write_parquet(cache / f"yahoo_{name}.parquet")
    (cache / "yahoo_settings.json").write_text(json.dumps(tables["settings"], indent=2), encoding="utf-8")


def _merge_existing(existing: dict, incoming: dict, prefix: str, conflicts: list[dict]) -> None:
    for key, value in incoming.items():
        path = f"{prefix}.{key}"
        if key not in existing:
            existing[key] = value
        elif isinstance(existing[key], dict) and isinstance(value, dict):
            _merge_existing(existing[key], value, path, conflicts)
        elif existing[key] != value:
            conflicts.append({"key": path, "existing": existing[key], "api": value})


def _complete_import(tables: dict, expected_teams: int) -> bool:
    return (
        tables["teams"].height == expected_teams
        and tables["rosters"].get_column("team_id").n_unique() == expected_teams
        and tables["standings"].get_column("team_id").n_unique() == expected_teams
        and not tables["schedule"].is_empty()
    )


def _diff_report(conflicts: list[dict]) -> str:
    lines = ["# Yahoo load differences", ""]
    if not conflicts:
        lines.append("- None.")
    else:
        lines.append("Existing pasted/config values were kept for these conflicts:")
        lines.append("")
        for row in conflicts:
            lines.append(
                f"- `{row['key']}` — existing: `{row['existing']}`; "
                f"Yahoo API: `{row['api']}`"
            )
    return "\n".join(lines) + "\n"


def merged_config(config: dict, settings: dict, complete: bool) -> tuple[dict, list[dict]]:
    """Merge Yahoo settings without overwriting existing pasted values."""
    result = json.loads(json.dumps(config))
    conflicts = []
    league_settings = {key: value for key, value in settings.items() if key != "scoring"}
    _merge_existing(result.setdefault("league", {}), league_settings, "league", conflicts)
    _merge_existing(
        result.setdefault("scoring", {}), settings.get("scoring", {}),
        "scoring", conflicts,
    )
    result["league"]["partial_import"] = not complete
    return result, conflicts


def update_config(config_path: Path, settings: dict, complete: bool = False) -> list[dict]:
    """Atomically merge Yahoo settings into config and return conflicts."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    merged, conflicts = merged_config(config, settings, complete)
    temporary = config_path.with_suffix(config_path.suffix + ".tmp")
    temporary.write_text(yaml.safe_dump(merged, sort_keys=False), encoding="utf-8")
    os.replace(temporary, config_path)
    return conflicts


def load_yahoo_tables(
    tables: dict,
    config_path: Path,
    cache: Path,
    diff_path: Path,
    now: datetime | None = None,
) -> Path:
    """Back up config, then merge settings and save validated tables."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    expected_teams = int(config["league"]["teams"])
    complete = _complete_import(tables, expected_teams)
    timestamp = (now or datetime.now()).strftime("%Y%m%dT%H%M%S")
    backup = config_path.with_name(f"{config_path.name}.pre-yahoo-{timestamp}")
    shutil.copy2(config_path, backup)
    save_tables(tables, cache)
    conflicts = update_config(config_path, tables["settings"], complete=complete)
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff_path.write_text(_diff_report(conflicts), encoding="utf-8")
    return backup


def load_yahoo_payload(
    payload: dict,
    ids: pl.DataFrame,
    config_path: Path,
    cache: Path,
    diff_path: Path,
    now: datetime | None = None,
) -> tuple[Path, dict]:
    """Parse and validate every Yahoo table before making any writes."""
    try:
        tables = parse_yahoo_payload(payload, ids)
    except YahooTableError:
        raise
    except Exception as exc:
        raise YahooTableError("settings", str(exc)) from exc
    backup = load_yahoo_tables(tables, config_path, cache, diff_path, now=now)
    return backup, tables
