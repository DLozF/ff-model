import argparse
import json
import re
from pathlib import Path

import polars as pl
import yaml

from ffm.yahoo_paste import match_roster, parse_roster_text, parse_settings_text

ROOT = Path("/opt/data/ff-model")
PASTE = ROOT / "data/yahoo_paste"
CACHE = ROOT / "data/cache"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partial", action="store_true", required=True)
    args = parser.parse_args()
    if not args.partial:
        raise SystemExit("only --partial mode is implemented")

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


if __name__ == "__main__":
    main()
