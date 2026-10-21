import csv
import io
import re
import unicodedata

import polars as pl

from ffm.ids import normalize_team


POSITION_MAP = {"W/R/T": "FLEX"}
PLAYER_LINE = re.compile(
    r"^(?P<name>.+?)(?:No new player Notes?|New Player Note|Player Note)\s+"
    r"(?P<team>[A-Za-z]{2,3})\s*-\s*(?P<pos>QB|RB|WR|TE|K|DEF)\b",
    re.IGNORECASE,
)
SCORING_LABELS = {
    "Passing Touchdowns": "pass_td", "Interceptions": "pass_int",
    "Rushing Touchdowns": "rush_td", "Receptions": "rec",
    "Receiving Touchdowns": "rec_td", "Return Touchdowns": "ret_td",
    "2-Point Conversions": "all_2pt", "Fumbles Lost": "fum_lost",
    "Offensive Fumble Return TD": "off_fum_ret_td",
    "40+ Yard Completions": "pass_cmp_40p", "40+ Yard Passing Touchdowns": "pass_td_40p",
    "40+ Yard Run": "rush_40p", "40+ Yard Rushing Touchdowns": "rush_td_40p",
    "40+ Yard Receptions": "rec_40p", "40+ Yard Receiving Touchdowns": "rec_td_40p",
    "Field Goals 0-19 Yards": "fgm_0_19", "Field Goals 20-29 Yards": "fgm_20_29",
    "Field Goals 30-39 Yards": "fgm_30_39", "Field Goals 40-49 Yards": "fgm_40_49",
    "Field Goals 50+ Yards": "fgm_50p", "Point After Attempt Made": "xpm",
    "4th Down Stops": "def_fourth_down_stop", "Extra Point Returned": "def_xp_return",
}
IDP_LABELS = {
    "Tackle Solo": "tackle_solo", "Tackle Assist": "tackle_assist", "Sack": "sack",
    "Interception": "interception", "Fumble Force": "fumble_force",
    "Fumble Recovery": "fumble_recovery", "Defensive Touchdown": "defensive_td",
    "Safety": "safety", "Pass Defended": "pass_defended", "Block Kick": "block_kick",
    "Tackles for Loss": "tackle_for_loss", "Turnover Return Yards": "turnover_return_yd",
    "Extra Point Returned": "xp_return",
}


def normalize_player_name(name: str) -> str:
    """Normalize accents, punctuation, and common suffixes for matching."""
    value = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-z0-9 ]+", " ", value.lower())
    value = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_available_text(text: str) -> tuple[pl.DataFrame, list[str]]:
    """Parse concatenated Yahoo available-player pages and return unparsed lines."""
    records = []
    unparsed = []
    seen = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = PLAYER_LINE.search(line)
        if not match:
            unparsed.append(line)
            continue
        name = re.sub(
            r"(?:IR-R|IR|PUP|NA|Q|D|O)$", "", match.group("name").strip()
        ).strip()
        record = {
            "name": name,
            "nfl_team": normalize_team(match.group("team")),
            "pos": match.group("pos").upper(),
        }
        key = (normalize_player_name(name), record["nfl_team"], record["pos"])
        if key not in seen:
            records.append(record)
            seen.add(key)
    return pl.from_dicts(records, infer_schema_length=None), unparsed


def _player_record(line: str) -> dict | None:
    match = PLAYER_LINE.search(line.strip())
    if not match:
        return None
    name = re.sub(r"(?:IR-R|IR|PUP|NA|Q|D|O)$", "", match.group("name").strip()).strip()
    return {
        "name": name,
        "nfl_team": normalize_team(match.group("team")),
        "pos": match.group("pos").upper(),
    }


def parse_roster_page(text: str) -> tuple[str | None, pl.DataFrame, list[str]]:
    """Parse a raw Yahoo team roster page while retaining lineup slots."""
    team_name = None
    records = []
    unparsed = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        team_match = re.match(r"^(?:Team|Fantasy Team)\s*:\s*(.+)$", line, re.IGNORECASE)
        if team_match:
            team_name = team_match.group(1).strip()
            continue
        if line.lower() in {"players", "player", "roster", "status", "pos"}:
            continue
        slot_match = re.match(r"^(QB|RB|WR|TE|W/R/T|K|DEF|D|BN|IR)\s+(.+)$", line, re.IGNORECASE)
        if not slot_match:
            unparsed.append(line)
            continue
        slot = slot_match.group(1).upper()
        record = _player_record(slot_match.group(2))
        if record is None:
            unparsed.append(line)
            continue
        records.append({"slot": slot, **record})
    schema = {"slot": pl.String, "name": pl.String, "nfl_team": pl.String, "pos": pl.String}
    return team_name, pl.from_dicts(records, schema=schema), unparsed


def parse_standings_text(text: str) -> tuple[pl.DataFrame, dict[str, int], list[str]]:
    """Parse Yahoo standings into team IDs and current records."""
    records = []
    unparsed = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.lower() in {"standings", "rank team w-l-t points", "rank"}:
            continue
        parts = [part.strip() for part in line.split("\t") if part.strip()]
        if len(parts) >= 4:
            rank_text, team_name, record_text, points_text = parts[:4]
            record = re.fullmatch(r"(\d+)\s*-\s*(\d+)(?:\s*-\s*(\d+))?", record_text)
            if rank_text.isdigit() and record:
                records.append({
                    "team_id": int(rank_text), "team_name": team_name,
                    "wins": int(record.group(1)), "losses": int(record.group(2)),
                    "ties": int(record.group(3) or 0), "points_for": float(points_text.replace(",", "")),
                    "rank": int(rank_text),
                })
                continue
        match = re.match(
            r"^(?P<rank>\d+)\s+(?P<team>.+?)\s+(?P<w>\d+)-(?P<l>\d+)(?:-(?P<t>\d+))?\s+(?P<points>[\d,]+(?:\.\d+)?)$",
            line,
        )
        if match:
            records.append({
                "team_id": int(match.group("rank")), "team_name": match.group("team").strip(),
                "wins": int(match.group("w")), "losses": int(match.group("l")),
                "ties": int(match.group("t") or 0), "points_for": float(match.group("points").replace(",", "")),
                "rank": int(match.group("rank")),
            })
        else:
            unparsed.append(line)
    frame = pl.from_dicts(records, schema={
        "team_id": pl.Int64, "team_name": pl.String, "wins": pl.Int64,
        "losses": pl.Int64, "ties": pl.Int64, "points_for": pl.Float64, "rank": pl.Int64,
    })
    teams = {normalize_player_name(row["team_name"]): int(row["team_id"]) for row in records}
    return frame, teams, unparsed


def parse_schedule_text(text: str, teams: dict[str, int]) -> tuple[pl.DataFrame, list[str]]:
    """Parse one or more Yahoo matchup pages using standings team IDs."""
    week = None
    records = []
    unparsed = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        week_match = re.match(r"^Week\s+(\d+)", line, re.IGNORECASE)
        if week_match:
            week = int(week_match.group(1))
            continue
        matchup = re.split(r"\s+(?:vs\.?|at)\s+|\t+(?:vs\.?|at)\t+", line, maxsplit=1, flags=re.IGNORECASE)
        if week is None or len(matchup) != 2:
            unparsed.append(line)
            continue
        left, right = (normalize_player_name(value) for value in matchup)
        if left not in teams or right not in teams:
            unparsed.append(line)
            continue
        records.append({"week": week, "team1_id": teams[left], "team2_id": teams[right]})
    frame = pl.from_dicts(records, schema={"week": pl.Int64, "team1_id": pl.Int64, "team2_id": pl.Int64})
    return frame, unparsed


def _rows(text: str) -> dict[str, str]:
    result = {}
    for line in text.splitlines():
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) >= 2 and parts[0]:
            result[parts[0].rstrip(":")] = parts[1]
    return result


def _number(value: str) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if not match:
        raise ValueError(f"no numeric value in {value!r}")
    return float(match.group())


def _milestones(value: str) -> list[dict]:
    return [
        {"threshold": int(threshold), "points": float(points)}
        for points, threshold in re.findall(r"(\d+(?:\.\d+)?) points? at (\d+) yards", value)
    ]


def parse_settings_text(text: str) -> dict:
    """Parse league settings copied from Yahoo's settings page."""
    rows = _rows(text)
    slots = [slot.strip() for slot in rows["Roster Positions"].split(",")]
    lineup = {}
    bench = slots.count("BN")
    ir_slots = slots.count("IR") + slots.count("IR+")
    for slot in slots:
        position = POSITION_MAP.get(slot, slot)
        if position not in {"BN", "IR", "IR+"}:
            lineup[position] = lineup.get(position, 0) + 1
    playoff_text = rows["Playoffs"]
    playoff_teams = int(_number(playoff_text))
    week_text = playoff_text.split("Week", 1)[1].split("(", 1)[0]
    playoff_weeks = [int(value) for value in re.findall(r"\d+", week_text)]
    scoring = {
        "pass_yd": 1 / 25, "rush_yd": 0.1, "rec_yd": 0.1,
        "pass_2pt": 2, "rush_2pt": 2, "rec_2pt": 2,
        "def_pts_allowed": {"0": 10, "1-6": 7, "7-13": 4, "14-20": 1,
                               "21-27": 0, "28-34": -1, "35+": -4},
        "milestone_mode": "highest",
        "pass_yd_milestones": _milestones(rows.get("Passing Yards", "")),
        "rush_yd_milestones": _milestones(rows.get("Rushing Yards", "")),
        "rec_yd_milestones": _milestones(rows.get("Receiving Yards", "")),
    }
    section = "offense"
    idp = {}
    defense = {}
    for line in text.splitlines():
        parts = [part.strip() for part in line.split("\t")]
        label = parts[0] if parts else ""
        if label == "Defensive Players":
            section = "idp"
            continue
        if label in {"Offense", "Kickers", "Defense/Special Teams"}:
            section = label.lower()
            continue
        value = parts[1] if len(parts) >= 2 else None
        if not value:
            continue
        if section == "idp" and label in IDP_LABELS:
            idp[IDP_LABELS[label]] = _number(value)
        elif section == "defense/special teams":
            defense_key = {
                "Sack": "def_sack", "Interception": "def_int",
                "Fumble Recovery": "def_fum_rec", "Touchdown": "def_td",
                "Safety": "def_safety", "Block Kick": "def_blk_kick",
                "Kickoff and Punt Return Touchdowns": "def_kr_pr_td",
                "4th Down Stops": "def_fourth_down_stop",
                "Extra Point Returned": "def_xp_return",
            }.get(label)
            if defense_key:
                defense[defense_key] = _number(value)
        elif label in SCORING_LABELS:
            key = SCORING_LABELS[label]
            if key == "all_2pt":
                scoring.update({"pass_2pt": _number(value), "rush_2pt": _number(value), "rec_2pt": _number(value)})
            else:
                scoring[key] = _number(value)
    scoring.update({
        "def_sack": 1, "def_int": 2, "def_fum_rec": 2, "def_td": 6,
        "def_safety": 2, "def_blk_kick": 2, "def_kr_pr_td": 6,
        **defense,
    })
    trade_date = rows.get("Trade End Date")
    return {
        "league": {
            "teams": int(_number(rows["Max Teams"])), "lineup": lineup, "bench": bench,
            "ir_slots": ir_slots, "playoff_teams": playoff_teams,
            "playoff_weeks": playoff_weeks, "tiebreaker": "higher_seed",
            "playoff_reseeding": rows.get("Playoff Reseeding", "No").lower() == "yes",
            "waiver_type": "rolling" if "rolling" in rows.get("Waiver Type", "").lower() else "unknown",
            "waiver_days": int(_number(rows.get("Waiver Time", "0"))),
            "weekly_waivers": rows.get("Weekly Waivers"), "trade_deadline": trade_date,
            "draft_pick_trades": rows.get("Allow Draft Pick Trades", "No") == "Yes",
            "trade_review": rows.get("Trade Review", "None"),
        },
        "scoring": scoring, "idp_scoring": idp,
        "assumptions": ["Milestone bonus tiers use only the highest reached tier; stacked scoring is also implemented for comparison."],
        "needs_diego": ["Confirm whether yardage milestone bonus tiers stack or only the highest tier counts."],
    }


def parse_roster_text(text: str) -> pl.DataFrame:
    """Read the cleaned roster CSV after its comment header."""
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    rows = list(csv.DictReader(io.StringIO("\n".join(lines))))
    return pl.from_dicts(rows, infer_schema_length=None).with_columns(
        pl.col("bye").cast(pl.Int64), pl.col("yahoo_proj_w7").cast(pl.Float64),
        pl.col("pct_start").cast(pl.Float64), pl.col("pct_rostered").cast(pl.Float64),
    )


def match_roster(roster: pl.DataFrame, players: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Match pasted roster rows to Sleeper IDs without silent guesses."""
    candidates = players.select("player_id", "full_name", "position", "team").to_dicts()
    records = []
    for row in roster.iter_rows(named=True):
        result = {**row, "sleeper_id": None, "match_method": None, "model_excluded": row["slot"] == "D"}
        if row["pos"] == "DEF":
            result.update(sleeper_id=normalize_team(row["nfl_team"]), match_method="defense-team")
        elif row["slot"] != "D":
            name = normalize_player_name(row["name"])
            exact = [p for p in candidates if normalize_player_name(p["full_name"]) == name and p["position"] == row["pos"] and normalize_team(p["team"]) == normalize_team(row["nfl_team"])]
            fallback = [p for p in candidates if normalize_player_name(p["full_name"]) == name and p["position"] == row["pos"]]
            found = exact[0] if len(exact) == 1 else fallback[0] if len(fallback) == 1 else None
            if found:
                result.update(sleeper_id=str(found["player_id"]), match_method="name+position+team" if exact else "name+position")
        records.append(result)
    matched = pl.from_dicts(records, infer_schema_length=None)
    unresolved = matched.filter(pl.col("sleeper_id").is_null() & ~pl.col("model_excluded"))
    return matched, unresolved
