import time
from pathlib import Path
from typing import Any

import polars as pl
import requests

from ffm.ids import normalize_team

BASE = "https://api.sleeper.app"
POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}


def get_json(urls: str | list[str], attempts: int = 5) -> Any:
    """Fetch JSON with bounded retries and endpoint fallback."""
    choices = [urls] if isinstance(urls, str) else urls
    last_error = None
    for url in choices:
        for attempt in range(attempts):
            try:
                response = requests.get(url, timeout=60)
                response.raise_for_status()
                data = response.json()
                if data:
                    time.sleep(0.5)
                    return data
                last_error = RuntimeError(f"empty response from {url}")
            except (requests.RequestException, ValueError) as error:
                last_error = error
            time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"Sleeper fetch failed: {last_error}")


def projection_records(payload: list[dict]) -> list[dict]:
    """Flatten Sleeper projection records."""
    records = []
    for row in payload:
        player = row.get("player") or {}
        position = player.get("position")
        if row.get("category") != "proj" or position not in POSITIONS:
            continue
        name = player.get("full_name") or " ".join(
            value for value in (player.get("first_name"), player.get("last_name")) if value
        )
        record = {
            "player_id": str(row["player_id"]),
            "season": int(row["season"]),
            "week": int(row["week"]),
            "team": normalize_team(row.get("team")),
            "opponent": normalize_team(row.get("opponent")),
            "name": name,
            "position": position,
        }
        record.update(row.get("stats") or {})
        records.append(record)
    return records


def stat_records(payload: dict[str, dict]) -> list[dict]:
    """Flatten Sleeper stat records."""
    return [{"player_id": str(player_id), **stats} for player_id, stats in payload.items()]


def player_records(payload: dict[str, dict]) -> list[dict]:
    """Flatten the Sleeper player dictionary."""
    fields = (
        "full_name", "first_name", "last_name", "position", "team", "gsis_id",
        "yahoo_id", "injury_status", "status", "active",
    )
    return [
        {"player_id": str(player_id), **{field: player.get(field) for field in fields}}
        for player_id, player in payload.items()
    ]


def _write_records(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pl.from_dicts(records, infer_schema_length=None).write_parquet(path)


def cache_week(season: int, week: int, kind: str, cache: Path) -> Path:
    """Cache one Sleeper projection or stats week as Parquet."""
    path = cache / f"sleeper_{kind}_{season}_w{week:02d}.parquet"
    if path.exists():
        return path
    if kind == "projections":
        urls = [
            f"{BASE}/projections/nfl/{season}/{week}?season_type=regular",
            f"{BASE}/v1/projections/nfl/regular/{season}/{week}",
        ]
        records = projection_records(get_json(urls))
    elif kind == "stats":
        urls = [
            f"{BASE}/v1/stats/nfl/regular/{season}/{week}",
            f"{BASE}/stats/nfl/{season}/{week}?season_type=regular",
        ]
        records = stat_records(get_json(urls))
    else:
        raise ValueError(f"unknown kind: {kind}")
    if not records:
        raise RuntimeError(f"no {kind} records for {season} week {week}")
    _write_records(records, path)
    return path


def cache_players(cache: Path) -> Path:
    """Cache Sleeper's NFL player dictionary."""
    path = cache / "sleeper_players.parquet"
    if not path.exists():
        _write_records(player_records(get_json(f"{BASE}/v1/players/nfl")), path)
    return path


def cache_state(cache: Path) -> dict:
    """Cache and return the current Sleeper NFL state."""
    state = get_json(f"{BASE}/v1/state/nfl")
    pl.from_dicts([state], infer_schema_length=None).write_parquet(cache / "sleeper_state.parquet")
    return state
