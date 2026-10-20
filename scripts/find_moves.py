import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from ffm.config import load_config
from ffm.finder import trade_candidates, waiver_candidates
from ffm.market import (
    acceptance_label,
    healthy_market_fallers,
    load_market,
    market_ratio,
    news_lines,
    package_value,
    write_model_vs_market,
)
from ffm.season import roster_team_scores, simulate_team_scores
from ffm.trade import (
    apply_trade, fragility_label, metric_delta, roster_welp,
    stress_worlds, trade_verdict,
)
from ffm.worlds import load_injury_overrides, load_world_directory

ROOT = Path("/opt/data/ff-model")


def paired_summary(before, after, team):
    """Return paired playoff and championship deltas."""
    return {
        "playoffs": metric_delta(before["playoff"][:, team], after["playoff"][:, team]),
        "champion": metric_delta(before["champion_flags"][:, team], after["champion_flags"][:, team]),
    }


def main():
    started = time.perf_counter()
    config = load_config()
    world_dir = load_world_directory(ROOT / "models/world_manifest.json")
    points = np.load(world_dir / "points.npy", mmap_mode="r")
    available = np.load(world_dir / "available.npy", mmap_mode="r")
    projections = np.load(world_dir / "proj_seen.npy", mmap_mode="r")
    weeks = np.load(world_dir / "week_numbers.npy").tolist()
    players = pl.read_parquet(world_dir / "player_index.parquet")
    market = load_market(ROOT / "data/cache")
    sleeper_players = pl.read_parquet(ROOT / "data/cache/sleeper_players.parquet")
    news = healthy_market_fallers(market, sleeper_players)
    write_model_vs_market(players, market, ROOT / "reports/model_vs_market.md")
    league = json.loads((ROOT / "models/synthetic_league.json").read_text())
    names = [row["name"] or row["player_id"] for row in players.iter_rows(named=True)]
    positions = players.get_column("position").to_numpy()
    ros = players.get_column("ros_points").to_numpy()
    market_lookup = dict(zip(market.get_column("sleeper_id"), market.get_column("market_value")))
    player_values = np.array([
        market_lookup.get(str(player_id), 0.0) for player_id in players.get_column("player_id")
    ])
    overrides = load_injury_overrides(ROOT / "overrides.yaml")
    pending_overrides = [
        row for row in overrides if str(row.get("weeks", "")).upper() == "TBD"
    ]
    n_dev = config["sim"]["n_dev"]
    my_team = league["teams"].index(config["league"]["my_team"])
    rosters = league["rosters"]
    free_agents = league["free_agents"]
    cache = {}

    def welp(roster):
        key = tuple(sorted(roster))
        if key not in cache:
            cache[key] = roster_welp(
                points, projections, available, positions, list(key), n_dev
            )
        return cache[key]

    baseline = [welp(roster) for roster in rosters]
    screened = []
    candidate_count = 0
    market_pass = 0
    for other_team in range(len(rosters)):
        if other_team == my_team:
            continue
        for give, get in trade_candidates(rosters[my_team], rosters[other_team]):
            candidate_count += 1
            other_receives_value = package_value(player_values[list(give)])
            other_gives_value = package_value(player_values[list(get)])
            ratio = market_ratio(other_receives_value, other_gives_value)
            if not ratio >= 0.9:
                continue
            market_pass += 1
            raw_my = [player for player in rosters[my_team] if player not in give] + list(get)
            raw_other = [player for player in rosters[other_team] if player not in get] + list(give)
            if welp(raw_my) <= baseline[my_team] or welp(raw_other) < baseline[other_team]:
                continue
            updated, adjustments = apply_trade(
                rosters, free_agents, my_team, other_team, list(give), list(get),
                points, projections, available, positions, ros, n_dev,
            )
            my_gain = welp(updated[my_team]) - baseline[my_team]
            other_gain = welp(updated[other_team]) - baseline[other_team]
            if my_gain > 0 and other_gain >= 0:
                screened.append({
                    "other_team": other_team, "give": give, "get": get,
                    "rosters": updated, "adjustments": adjustments,
                    "my_welp": my_gain, "other_welp": other_gain,
                    "ratio": ratio, "other_receives_value": other_receives_value,
                    "other_gives_value": other_gives_value,
                })
    screened.sort(key=lambda row: row["my_welp"], reverse=True)
    base_scores = np.stack([
        roster_team_scores(points, projections, available, positions, roster)
        for roster in rosters
    ], axis=2)
    before = simulate_team_scores(base_scores, weeks, 14, 6)
    stress_points, stress_available = stress_worlds(points, available, positions)
    stress_base_scores = np.stack([
        roster_team_scores(stress_points, projections, stress_available, positions, roster)
        for roster in rosters
    ], axis=2)
    stress_before = simulate_team_scores(stress_base_scores, weeks, 14, 6)
    criterion = "champion" if before["playoff"][:, my_team].mean() > 0.9 else "playoffs"
    confirmed = []
    for row in screened[:30]:
        changed = (my_team, row["other_team"])
        after_scores = base_scores.copy()
        stress_after_scores = stress_base_scores.copy()
        for team in changed:
            after_scores[:, :, team] = roster_team_scores(
                points, projections, available, positions, row["rosters"][team]
            )
            stress_after_scores[:, :, team] = roster_team_scores(
                stress_points, projections, stress_available, positions,
                row["rosters"][team],
            )
        after = simulate_team_scores(after_scores, weeks, 14, 6)
        mine = paired_summary(before, after, my_team)
        other = paired_summary(before, after, row["other_team"])
        verdict = trade_verdict(mine[criterion])
        stress_after = simulate_team_scores(stress_after_scores, weeks, 14, 6)
        stress_mine = paired_summary(stress_before, stress_after, my_team)
        stress_verdict = trade_verdict(stress_mine[criterion])
        fragility, fragility_reason = fragility_label(verdict, stress_verdict)
        acceptance = acceptance_label(row["ratio"])
        if verdict == "ACCEPT":
            confirmed.append({
                **row, "mine": mine, "other": other, "verdict": verdict,
                "acceptance": acceptance, "stress_verdict": stress_verdict,
                "fragility": fragility, "fragility_reason": fragility_reason,
            })
    confirmed.sort(key=lambda row: row["mine"][criterion]["mean"], reverse=True)

    top_free_agents = sorted(free_agents, key=lambda player: ros[player], reverse=True)[:40]
    waiver_screen = []
    for drop, add in waiver_candidates(top_free_agents, rosters[my_team]):
        updated_roster = [player for player in rosters[my_team] if player != drop] + [add]
        gain = welp(updated_roster) - baseline[my_team]
        if gain > 0:
            waiver_screen.append((gain, drop, add, updated_roster))
    waiver_screen.sort(reverse=True)
    waiver_results = []
    for gain, drop, add, updated_roster in waiver_screen[:10]:
        updated = [list(roster) for roster in rosters]
        updated[my_team] = updated_roster
        after_scores = base_scores.copy()
        after_scores[:, :, my_team] = roster_team_scores(
            points, projections, available, positions, updated_roster
        )
        after = simulate_team_scores(after_scores, weeks, 14, 6)
        mine = paired_summary(before, after, my_team)
        waiver_results.append({
            "gain": gain, "drop": drop, "add": add, "mine": mine,
            "verdict": trade_verdict(mine[criterion]),
        })

    date = datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
    trade_lines = [f"# Trade ideas: {date}", "", *news_lines(news)]
    trade_lines.extend(["## Injury overrides needing Diego's input", ""])
    if pending_overrides:
        trade_lines.extend(
            f"- {row['name']}: weeks is TBD; override not applied. Note: {row.get('note', '')}."
            for row in pending_overrides
        )
    else:
        trade_lines.append("- None.")
    trade_lines.extend([
        "", "## Trade results", "",
        f"Screened {candidate_count} trades; {market_pass} passed market r >= 0.90; "
        f"{len(screened)} passed WELP; confirmed top {min(30, len(screened))}.",
        "", "Stress case: score spread ×1.25; QB availability thinned by one-seventh.",
        "", "| Rank | Partner | Give | Get | Other receives V | Other gives V | r | WELP gain | Verdict metric gain | Other model playoff delta | Verdict | Stress | Stability | Acceptance |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---|---|---|",
    ])
    for rank, row in enumerate(confirmed, 1):
        trade_lines.append(
            f"| {rank} | {league['teams'][row['other_team']]} | "
            f"{', '.join(names[player] for player in row['give'])} | "
            f"{', '.join(names[player] for player in row['get'])} | "
            f"{row['other_receives_value']:.1f} | {row['other_gives_value']:.1f} | "
            f"{row['ratio']:.3f}{' OVERPAY' if row['ratio'] > 1.25 else ''} | {row['my_welp']:+.2f} | "
            f"{row['mine'][criterion]['mean']:+.4f} | {row['other']['playoffs']['mean']:+.4f} | "
            f"{row['verdict']} | {row['stress_verdict']} | "
            f"{row['fragility']}: {row['fragility_reason']} | {row['acceptance']} |"
        )
    if not confirmed:
        trade_lines.append("| - | - | - | - | - | - | - | - | - | - | No qualifying trades | - | - | - |")
    (ROOT / "reports" / f"trade_ideas_{date}.md").write_text("\n".join(trade_lines) + "\n", encoding="utf-8")

    waiver_lines = [
        f"# Waiver ideas: {date}", "", *news_lines(news),
        "## Injury overrides needing Diego's input", "",
    ]
    if pending_overrides:
        waiver_lines.extend(
            f"- {row['name']}: weeks is TBD; override not applied. Note: {row.get('note', '')}."
            for row in pending_overrides
        )
    else:
        waiver_lines.append("- None.")
    waiver_lines.extend([
        "", "## Waiver results", "",
        f"Screened {len(top_free_agents) * len(rosters[my_team])} add/drop pairs; confirmed top {min(10, len(waiver_screen))}.",
        "", "| Rank | Add | Drop | Add V | Drop V | WELP gain | Verdict metric gain | Verdict |",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ])
    for rank, row in enumerate(waiver_results, 1):
        waiver_lines.append(
            f"| {rank} | {names[row['add']]} | {names[row['drop']]} | "
            f"{player_values[row['add']]:.1f} | {player_values[row['drop']]:.1f} | {row['gain']:+.2f} | "
            f"{row['mine'][criterion]['mean']:+.4f} | {row['verdict']} |"
        )
    if not waiver_results:
        waiver_lines.append("| - | - | - | - | - | - | - | No positive WELP moves |")
    (ROOT / "reports" / f"waivers_{date}.md").write_text("\n".join(waiver_lines) + "\n", encoding="utf-8")
    runtime = time.perf_counter() - started
    print(f"trade_candidates: {candidate_count}")
    print(f"trade_market_pass: {market_pass}")
    print(f"trade_welp_pass: {len(screened)}")
    print(f"trade_final: {len(confirmed)}")
    print(f"waiver_final: {len(waiver_results)}")
    print(f"runtime_seconds: {runtime:.3f}")


if __name__ == "__main__":
    main()
