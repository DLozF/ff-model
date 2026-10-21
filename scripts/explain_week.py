"""Explain one player-week: pregame inputs, model prediction, and actual scoring."""
import argparse
import json
from pathlib import Path

import numpy as np
import polars as pl
import yaml

from ffm.actuals import merge_actual_sources
from ffm.ids import normalize_team
from ffm.own_projection import ewma
from ffm.pbp_bonus import aggregate_bonus_stats, merge_bonus_stats
from ffm.scoring import fantasy_points, nflverse_stat_line

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def resolve_player(name: str, players: pl.DataFrame):
    """Return the unique Sleeper player for a name, or None with candidates."""
    needle = (
        name.lower().replace(".", "").replace("'", "").replace(" jr", "").strip()
    )
    found = players.filter(
        pl.col("full_name").str.to_lowercase().str.replace_all(r"\.", "")
        .str.replace_all("'", "").str.replace_all(r"\s+jr\.?$", "").str.strip_chars()
        .str.contains(needle)
        & pl.col("position").is_in(("QB", "RB", "WR", "TE", "K", "DEF"))
    )
    if found.height != 1:
        return None, [dict(row) for row in found.select("player_id", "full_name", "position", "team").iter_rows(named=True)]
    return found.row(0, named=True), []


def pct(value: float, total: float) -> float:
    return float(value / total) if total else 0.0


def pregame_features(player: dict, frame: pl.DataFrame, snaps: pl.DataFrame, opportunity: pl.DataFrame, schedules: pl.DataFrame, injuries: pl.DataFrame) -> dict:
    season, week = player["season"], player["week"]
    history = frame.filter(
        (pl.col("sleeper_id") == player["sleeper_id"])
        & ((pl.col("season") < season) | ((pl.col("season") == season) & (pl.col("week") < week)))
    ).sort("season", "week")
    points = history.get_column("act_pts").to_numpy()
    mine = snaps.filter(
        (pl.col("season") == season) & (pl.col("week") < week)
        & (pl.col("team") == player["team"])
        & (pl.col("player") == player["name"])
    ).drop_nulls("offense_pct")
    snap_share = float(mine.get_column("offense_pct").mean()) if mine.height else 0.0
    opp = opportunity.filter((pl.col("season") == season) & (pl.col("week") < week))
    opp_player = opp.filter(opp["player_id"] == player["gsis_id"]) if player["gsis_id"] else opp.head(0)
    team_pass = (
        opp.filter(pl.col("posteam") == player["team"])
        .group_by("week").agg(pl.col("pass_attempt_team").first().alias("attempts"))
    )
    targets = float(opp_player.get_column("rec_attempt").sum()) if opp_player.height else 0.0
    carries = float(opp_player.get_column("rush_attempt").sum()) if opp_player.height else 0.0
    game = schedules.filter(
        (pl.col("season") == season) & (pl.col("week") == week) & (pl.col("game_type") == "REG")
        & ((pl.col("home_team") == normalize_team(player["team"])) | (pl.col("away_team") == normalize_team(player["team"])))
    )
    if game.height:
        row = game.row(0, named=True)
        spread = float(row["spread_line"] or 0.0)
        total = float(row["total_line"] or 0.0)
        home = normalize_team(row["home_team"]) == normalize_team(player["team"])
        implied = (total + spread) / 2 if home else (total - spread) / 2
    else:
        spread, total, implied, home = 0.0, 0.0, 0.0, None
    injury = injuries.filter(
        (pl.col("season") == season) & (pl.col("week") == week) & (pl.col("gsis_id") == player["gsis_id"])
    )
    status = injury.get_column("report_status").item() if injury.height else None
    return {
        "sleeper_projection": player["proj_pts"],
        "last3_avg": float(np.mean(points[-3:])) if points.size else 0.0,
        "season_avg": float(np.mean(points)) if points.size else 0.0,
        "ewma": ewma(points, CONFIG.get("ewma_half_life", {}).get(player["pos"], 3.0)),
        "snap_share": round(snap_share, 4),
        "target_share": round(pct(targets, float(team_pass.get_column("attempts").sum() or 1)), 4),
        "carries": carries,
        "team_implied_points": implied,
        "spread": spread,
        "total": total,
        "home": home,
        "injury_status": status,
    }


def actual_breakdown(player: dict, stats: pl.DataFrame, pbp: pl.DataFrame, ids: pl.DataFrame) -> dict:
    """Rescore the actual game from raw stats plus play-by-play bonuses."""
    season, week = player["season"], player["week"]
    rows = stats.filter((pl.col("season") == season) & (pl.col("week") == week) & (pl.col("player_id") == player["gsis_id"]))
    if not rows.height:
        return {"played": False, "total": 0.0}
    row = rows.row(0, named=True)
    bonus = pbp.filter((pl.col("season") == season) & (pl.col("week") == week))
    sleeper_ids = pl.DataFrame({"gsis_id": [player["gsis_id"]], "sleeper_id": [str(player["sleeper_id"])]})
    aggregates = aggregate_bonus_stats(bonus, sleeper_ids)
    merged = merge_bonus_stats(
        pl.DataFrame({key: [value] for key, value in row.items() if isinstance(value, (int, float)) or key in ("season", "week", "player_id",)}),
        aggregates,
    )
    scored = fantasy_points(merged.row(0, named=True) | nflverse_stat_line(row), player["pos"], CONFIG["scoring"])
    return {
        "played": True,
        "total": float(scored),
        "pass_yd": row.get("passing_yards"), "pass_td": row.get("passing_tds"),
        "pass_int": row.get("passing_interceptions"), "rush_yd": row.get("rushing_yards"),
        "rush_td": row.get("rushing_tds"), "rec": row.get("receptions"),
        "rec_yd": row.get("receiving_yards"), "rec_td": row.get("receiving_tds"),
        "fum_lost": row.get("fumbles_lost_total"), "ret_td": row.get("special_teams_tds"),
        "pass_cmp_40p": merged.get_column("pass_cmp_40p").sum(),
        "rush_40p": merged.get_column("rush_40p").sum(), "rec_40p": merged.get_column("rec_40p").sum(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    args = parser.parse_args()

    frame = pl.read_parquet(CACHE / "player_weeks.parquet")
    players = pl.read_parquet(CACHE / "sleeper_players.parquet")
    candidate = players.filter(
        (pl.col("player_id").is_in(frame.get_column("sleeper_id").unique().to_list()))
        & (pl.col("position").is_in(("QB", "RB", "WR", "TE", "K", "DEF")))
    )
    player_row, others = resolve_player(args.player, candidate)
    if player_row is None:
        print(json.dumps({"error": "ambiguous", "candidates": others}, indent=2))
        raise SystemExit(1)
    weeks = frame.filter(
        (pl.col("sleeper_id").cast(pl.String) == str(player_row["player_id"]))
        & (pl.col("season") == args.season) & (pl.col("week") == args.week)
    )
    if not weeks.height:
        print(json.dumps({"error": "not in dataset"}, indent=2))
        raise SystemExit(1)
    player = {**weeks.row(0, named=True), "gsis_id": player_row["gsis_id"] or weeks.item(0, "gsis_id")}

    snaps = pl.read_parquet(CACHE / "nflverse_snap_counts.parquet")
    opportunity = pl.read_parquet(CACHE / "nflverse_ff_opportunity.parquet")
    schedules = pl.read_parquet(CACHE / "nflverse_schedules.parquet")
    injuries = pl.read_parquet(CACHE / "nflverse_injuries.parquet")
    stats = pl.read_parquet(CACHE / "nflverse_player_stats.parquet")
    ids = pl.read_parquet(CACHE / "nflverse_ff_playerids.parquet")
    pbp = pl.concat([
        pl.read_parquet(path) for path in sorted(CACHE.glob("nflverse_pbp_bonus_*.parquet"))
    ], how="diagonal_relaxed")

    features = pregame_features(player, frame, snaps, opportunity, schedules, injuries)
    actual = actual_breakdown(player, stats, pbp, ids)
    model = np.load(ROOT / "models/quantiles_2026.npz", allow_pickle=False)
    levels = model["levels"]
    table = model[f"{player['pos']}_quantiles"]
    grid = model[f"{player['pos']}_grid"]
    projection = np.interp(player["proj_pts"], grid, table[:, 99])
    p10 = np.interp(player["proj_pts"], grid, table[:, int(np.argmin(np.abs(levels - 0.1)))])
    p50 = np.interp(player["proj_pts"], grid, table[:, int(np.argmin(np.abs(levels - 0.5)))])
    p90 = np.interp(player["proj_pts"], grid, table[:, int(np.argmin(np.abs(levels - 0.9)))])

    played = actual.pop("played")
    error = actual["total"] - features["sleeper_projection"] if played else None
    inside = (
        float(np.searchsorted(np.sort(table[int(np.argmin(np.abs(grid - player["proj_pts"])))]), actual["total"]) / len(levels))
        if played else None
    )
    cause = "TD variance" if played and abs(error) > 6 else "within normal variance"
    if not played:
        cause = "did not play"

    (ROOT / "reports/explain").mkdir(parents=True, exist_ok=True)
    slug = args.player.lower().replace(" ", "_")
    body = {
        "player": player["name"], "season": args.season, "week": args.week,
        "pregame": features, "prediction": {"p10": float(p10), "p50": float(p50), "p90": float(p90)},
        "actual": actual, "played": played,
        "error": error, "percentile_of_actual": inside, "cause": cause,
    }
    (ROOT / f"reports/explain/{slug}_{args.season}_w{args.week}.md").write_text(
        "# " + player["name"] + "\n\n```json\n" + json.dumps(body, indent=2) + "\n```\n", encoding="utf-8"
    )
    print(json.dumps(body, indent=2))


if __name__ == "__main__":
    main()
