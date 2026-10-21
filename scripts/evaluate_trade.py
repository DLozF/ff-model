import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from ffm.config import load_config
from ffm.lineup import greedy
from ffm.market import (
    acceptance_cutoffs,
    acceptance_label,
    acceptance_status,
    healthy_market_fallers,
    load_market,
    market_ratio,
    news_lines,
    package_value,
)
from ffm.market_fallback import apply_model_fallback
from ffm.trade import (
    apply_trade, evaluate_rosters, fragility_label, fuzzy_match, metric_delta,
    roster_lineup_points, stress_worlds, trade_verdict,
)
from ffm.worlds import load_injury_overrides, load_world_directory

ROOT = Path("/opt/data/ff-model")


def parse_names(value):
    """Parse a comma-separated player list."""
    return [name.strip() for name in value.split(",") if name.strip()]


def exposure(points, projections, available, positions, nfl_teams, roster):
    """Measure lineup point shares by NFL team."""
    indices = np.asarray(roster)
    totals = {}
    grand = 0.0
    for week in range(points.shape[0]):
        selected = greedy(
            projections[week][:, indices], positions[indices], available[week][:, indices]
        )
        contributions = points[week][:, indices] * selected
        for team in sorted(set(nfl_teams[indices])):
            mask = nfl_teams[indices] == team
            value = float(contributions[:, mask].sum(axis=1).mean())
            totals[team] = totals.get(team, 0.0) + value
            grand += value
    return {team: value / grand for team, value in totals.items()} if grand else {}


def summarize(before, after, team):
    """Build paired metric summaries for one fantasy team."""
    return {
        "playoffs": metric_delta(before["playoff"][:, team], after["playoff"][:, team]),
        "champion": metric_delta(before["champion_flags"][:, team], after["champion_flags"][:, team]),
        "wins": metric_delta(before["wins"][:, team], after["wins"][:, team]),
        "missed_playoffs": metric_delta(~before["playoff"][:, team], ~after["playoff"][:, team]),
    }


def interval_text(value):
    return f"{value['mean']:+.4f} [{value['low']:+.4f}, {value['high']:+.4f}]"


def write_report(
    path, league, names, weeks, before, after, summaries, my_team, other_team,
    verdict, acceptance, adjustments, exposure_before, exposure_after, ratio,
    other_receives_value, other_gives_value, news, pending_overrides,
    stress_verdict, fragility, fragility_reason, give_details, get_details,
    acceptance_note,
):
    """Write a trade decision report."""
    lines = [
        f"# Trade evaluation: {league['teams'][other_team]}", "",
        "## Decision", "",
        f"- Verdict for {league['teams'][my_team]}: **{verdict}**",
        f"- Stress verdict: **{stress_verdict}** — **{fragility}** ({fragility_reason})",
        "- Stress case: score spread ×1.25; QB availability thinned by one-seventh.",
        f"- Other-team acceptance: **{acceptance}**",
        f"- {acceptance_note}",
        f"- Market ratio r: **{ratio:.3f}**{' — OVERPAY' if ratio > 1.25 else ''}",
        f"- Other team receives V: **{other_receives_value:.1f}**",
        f"- Other team gives V: **{other_gives_value:.1f}**",
        f"- Give values: {give_details or 'none'}",
        f"- Get values: {get_details or 'none'}",
        f"- Other-team model playoff delta (info only): "
        f"**{summaries[other_team]['playoffs']['mean']:+.4f}**", "",
    ]
    for team in (my_team, other_team):
        lines.extend([
            f"## {league['teams'][team]}", "",
            "| Metric | Delta | 90% interval |", "|---|---:|---:|",
        ])
        for metric, value in summaries[team].items():
            lines.append(f"| {metric} | {value['mean']:+.4f} | [{value['low']:+.4f}, {value['high']:+.4f}] |")
        dropped = ", ".join(names[player] for player in adjustments[team]["dropped"]) or "none"
        added = ", ".join(names[player] for player in adjustments[team]["added"]) or "none"
        lines.extend(["", f"Roster balancing: dropped {dropped}; added {added}.", ""])
    lines.extend([
        "## Starting lineup points", "",
        "| Week | Team | Before | After | Delta |", "|---:|---|---:|---:|---:|",
    ])
    for week_index, week in enumerate(weeks):
        section = "regular" if week <= 14 else "playoff"
        for team in (my_team, other_team):
            old = float(before["team_week_scores"][week_index, :, team].mean())
            new = float(after["team_week_scores"][week_index, :, team].mean())
            lines.append(f"| {week} ({section}) | {league['teams'][team]} | {old:.2f} | {new:.2f} | {new-old:+.2f} |")
    lines.extend(["", "## QB exposure: Team 1 lineup point share by NFL team", "", "| NFL team | Before | After |", "|---|---:|---:|"])
    for team in sorted(set(exposure_before) | set(exposure_after)):
        lines.append(f"| {team} | {exposure_before.get(team, 0):.3f} | {exposure_after.get(team, 0):.3f} |")
    lines.extend(["", "## Injury overrides needing Diego's input", ""])
    if pending_overrides:
        lines.extend(
            f"- {row['name']}: weeks is TBD; override not applied. Note: {row.get('note', '')}."
            for row in pending_overrides
        )
    else:
        lines.append("- None.")
    lines.extend(["", *news_lines(news)])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--team", required=True)
    parser.add_argument("--give", default="")
    parser.add_argument("--get", default="")
    args = parser.parse_args()
    config = load_config()
    world_dir = load_world_directory(ROOT / "models/world_manifest.json")
    points = np.load(world_dir / "points.npy", mmap_mode="r")
    available = np.load(world_dir / "available.npy", mmap_mode="r")
    projections = np.load(world_dir / "proj_seen.npy", mmap_mode="r")
    weeks = np.load(world_dir / "week_numbers.npy").tolist()
    players = pl.read_parquet(world_dir / "player_index.parquet")
    market = load_market(ROOT / "data/cache")
    sleeper_players = pl.read_parquet(ROOT / "data/cache/sleeper_players.parquet")
    overrides = load_injury_overrides(ROOT / "overrides.yaml")
    if not {"market_value_final", "value_source"}.issubset(players.columns):
        players = apply_model_fallback(
            players, market, sleeper_players,
            lineup=config["league"]["lineup"], overrides=overrides,
        )
    league = json.loads((ROOT / "models/synthetic_league.json").read_text())
    names = players.get_column("name").fill_null(players.get_column("player_id")).to_list()
    positions = players.get_column("position").to_numpy()
    nfl_teams = players.get_column("team").to_numpy()
    ros_points = players.get_column("ros_points").to_numpy()
    player_values = players.get_column("market_value_final").to_numpy()
    value_sources = players.get_column("value_source").to_list()
    my_team = league["teams"].index(config["league"]["my_team"])
    player_ids = players.get_column("player_id").cast(pl.String).to_list()
    news_targets = set(league["rosters"][my_team]) | set(
        sorted(league["free_agents"], key=lambda player: ros_points[player], reverse=True)[:15]
    )
    news = healthy_market_fallers(
        market, sleeper_players, {player_ids[player] for player in news_targets}
    )
    other_team = league["teams"].index(args.team)
    give = [fuzzy_match(name, names) for name in parse_names(args.give)]
    get = [fuzzy_match(name, names) for name in parse_names(args.get)]
    if any(player not in league["rosters"][my_team] for player in give):
        raise ValueError("a give player is not on Team 1")
    if any(player not in league["rosters"][other_team] for player in get):
        raise ValueError(f"a get player is not on {args.team}")
    print("Matched give:", [names[player] for player in give])
    print("Matched get:", [names[player] for player in get])
    updated, adjustments = apply_trade(
        league["rosters"], league["free_agents"], my_team, other_team, give, get,
        points, projections, available, positions, ros_points, config["sim"]["n_dev"],
    )
    before = evaluate_rosters(
        points, projections, available, positions, league["rosters"], weeks, 14, 6
    )
    after = evaluate_rosters(points, projections, available, positions, updated, weeks, 14, 6)
    summaries = {
        my_team: summarize(before, after, my_team),
        other_team: summarize(before, after, other_team),
    }
    criterion = "champion" if before["playoff"][:, my_team].mean() > 0.9 else "playoffs"
    verdict = trade_verdict(summaries[my_team][criterion])
    stress_points, stress_available = stress_worlds(points, available, positions)
    stress_before = evaluate_rosters(
        stress_points, projections, stress_available, positions,
        league["rosters"], weeks, 14, 6,
    )
    stress_after = evaluate_rosters(
        stress_points, projections, stress_available, positions, updated, weeks, 14, 6,
    )
    stress_summary = summarize(stress_before, stress_after, my_team)
    stress_verdict = trade_verdict(stress_summary[criterion])
    fragility, fragility_reason = fragility_label(verdict, stress_verdict)
    other_receives_value = package_value(player_values[give])
    other_gives_value = package_value(player_values[get])
    ratio = market_ratio(other_receives_value, other_gives_value)
    cutoffs = acceptance_cutoffs(ROOT / "data/trade_log.csv")
    acceptance = acceptance_label(ratio, cutoffs)
    pending_overrides = [
        row for row in overrides if str(row.get("weeks", "")).upper() == "TBD"
    ]
    before_exposure = exposure(
        points, projections, available, positions, nfl_teams, league["rosters"][my_team]
    )
    after_exposure = exposure(points, projections, available, positions, nfl_teams, updated[my_team])
    date = datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
    slug = re.sub(r"[^a-z0-9]+", "_", f"{args.team}_{'_'.join(args.give.split(','))}_{'_'.join(args.get.split(','))}".lower()).strip("_") or "empty"
    path = ROOT / "reports" / f"trade_{date}_{slug}.md"
    give_details = ", ".join(
        f"{names[player]} V={player_values[player]:.1f} ({value_sources[player]})"
        for player in give
    )
    get_details = ", ".join(
        f"{names[player]} V={player_values[player]:.1f} ({value_sources[player]})"
        for player in get
    )
    write_report(
        path, league, names, weeks, before, after, summaries, my_team, other_team,
        verdict, acceptance, adjustments, before_exposure, after_exposure, ratio,
        other_receives_value, other_gives_value, news, pending_overrides,
        stress_verdict, fragility, fragility_reason, give_details, get_details,
        acceptance_status(cutoffs),
    )
    print(
        f"Verdict: {verdict}; acceptance: {acceptance}; r={ratio:.3f}; "
        f"other receives V={other_receives_value:.1f}; gives V={other_gives_value:.1f}"
    )
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
