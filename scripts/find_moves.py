import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from ffm.config import load_config
from ffm.finder import trade_candidates, waiver_candidates
from ffm.trade import (
    apply_trade, evaluate_rosters, metric_delta, roster_welp, trade_verdict,
)
from ffm.worlds import load_world_directory

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
    league = json.loads((ROOT / "models/synthetic_league.json").read_text())
    names = [row["name"] or row["player_id"] for row in players.iter_rows(named=True)]
    positions = players.get_column("position").to_numpy()
    ros = players.get_column("ros_points").to_numpy()
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
    for other_team in range(len(rosters)):
        if other_team == my_team:
            continue
        for give, get in trade_candidates(rosters[my_team], rosters[other_team]):
            candidate_count += 1
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
                })
    screened.sort(key=lambda row: row["my_welp"], reverse=True)
    before = evaluate_rosters(points, projections, available, positions, rosters, weeks, 14, 6)
    criterion = "champion" if before["playoff"][:, my_team].mean() > 0.9 else "playoffs"
    confirmed = []
    for row in screened[:30]:
        after = evaluate_rosters(
            points, projections, available, positions, row["rosters"], weeks, 14, 6
        )
        mine = paired_summary(before, after, my_team)
        other = paired_summary(before, after, row["other_team"])
        verdict = trade_verdict(mine[criterion])
        other_delta = other["playoffs"]["mean"]
        acceptance = "LIKELY" if other_delta > 0 else "POSSIBLE" if other_delta > -0.01 else "UNLIKELY"
        if verdict == "ACCEPT" and acceptance in {"LIKELY", "POSSIBLE"}:
            confirmed.append({**row, "mine": mine, "other": other, "verdict": verdict, "acceptance": acceptance})
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
        after = evaluate_rosters(points, projections, available, positions, updated, weeks, 14, 6)
        mine = paired_summary(before, after, my_team)
        waiver_results.append({
            "gain": gain, "drop": drop, "add": add, "mine": mine,
            "verdict": trade_verdict(mine[criterion]),
        })

    date = datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
    trade_lines = [
        f"# Trade ideas: {date}", "",
        f"Screened {candidate_count} trades; {len(screened)} passed WELP; confirmed top {min(30, len(screened))}.",
        "", "| Rank | Partner | Give | Get | WELP gain | Verdict metric gain | Verdict | Acceptance |",
        "|---:|---|---|---|---:|---:|---|---|",
    ]
    for rank, row in enumerate(confirmed, 1):
        trade_lines.append(
            f"| {rank} | {league['teams'][row['other_team']]} | "
            f"{', '.join(names[player] for player in row['give'])} | "
            f"{', '.join(names[player] for player in row['get'])} | {row['my_welp']:+.2f} | "
            f"{row['mine'][criterion]['mean']:+.4f} | {row['verdict']} | {row['acceptance']} |"
        )
    if not confirmed:
        trade_lines.append("| - | - | - | - | - | - | No qualifying trades | - |")
    (ROOT / "reports" / f"trade_ideas_{date}.md").write_text("\n".join(trade_lines) + "\n", encoding="utf-8")

    waiver_lines = [
        f"# Waiver ideas: {date}", "",
        f"Screened {len(top_free_agents) * len(rosters[my_team])} add/drop pairs; confirmed top {min(10, len(waiver_screen))}.",
        "", "| Rank | Add | Drop | WELP gain | Verdict metric gain | Verdict |",
        "|---:|---|---|---:|---:|---|",
    ]
    for rank, row in enumerate(waiver_results, 1):
        waiver_lines.append(
            f"| {rank} | {names[row['add']]} | {names[row['drop']]} | {row['gain']:+.2f} | "
            f"{row['mine'][criterion]['mean']:+.4f} | {row['verdict']} |"
        )
    if not waiver_results:
        waiver_lines.append("| - | - | - | - | - | No positive WELP moves |")
    (ROOT / "reports" / f"waivers_{date}.md").write_text("\n".join(waiver_lines) + "\n", encoding="utf-8")
    runtime = time.perf_counter() - started
    print(f"trade_candidates: {candidate_count}")
    print(f"trade_welp_pass: {len(screened)}")
    print(f"trade_final: {len(confirmed)}")
    print(f"waiver_final: {len(waiver_results)}")
    print(f"runtime_seconds: {runtime:.3f}")


if __name__ == "__main__":
    main()
