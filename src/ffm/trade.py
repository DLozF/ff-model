from difflib import get_close_matches

import numpy as np

from ffm.season import simulate_season


def fuzzy_match(name: str, names: list[str]) -> int:
    """Return the index of the closest player name."""
    matches = get_close_matches(name, names, n=1, cutoff=0.45)
    if not matches:
        raise ValueError(f"no player matched {name!r}")
    return names.index(matches[0])


def roster_lineup_points(points, projections, available, positions, roster, worlds=None):
    """Return week-by-world starting lineup points for one roster."""
    indices = np.asarray(roster, dtype=int)
    count = points.shape[1] if worlds is None else min(worlds, points.shape[1])
    totals = np.empty((points.shape[0], count), dtype=np.float32)
    roster_positions = positions[indices]
    for week in range(points.shape[0]):
        projected = projections[week, :count][:, indices]
        active = available[week, :count][:, indices]
        scores = np.where(active, projected, -np.inf)
        selected = np.zeros_like(active)
        for position, slots in (("QB", 1), ("RB", 2), ("WR", 2), ("TE", 1), ("K", 1), ("DEF", 1)):
            eligible = np.flatnonzero(roster_positions == position)
            if not eligible.size:
                continue
            order = np.argsort(scores[:, eligible], axis=1)[:, ::-1][:, :slots]
            chosen = eligible[order]
            rows = np.broadcast_to(np.arange(count)[:, None], chosen.shape)
            valid = np.isfinite(scores[rows, chosen])
            selected[rows[valid], chosen[valid]] = True
        flex = np.isin(roster_positions, ["RB", "WR", "TE"])
        flex_scores = np.where(flex[None, :] & active & ~selected, projected, -np.inf)
        chosen_flex = np.argmax(flex_scores, axis=1)
        rows = np.arange(count)
        valid = np.isfinite(flex_scores[rows, chosen_flex])
        selected[rows[valid], chosen_flex[valid]] = True
        totals[week] = np.sum(points[week, :count][:, indices] * selected, axis=1)
    return totals


def roster_welp(points, projections, available, positions, roster, worlds=1000):
    """Compute world-expected lineup points over all remaining weeks."""
    return float(roster_lineup_points(
        points, projections, available, positions, roster, worlds
    ).sum(axis=0).mean())


def rebalance_roster(
    roster: list[int],
    free_agents: set[int],
    points: np.ndarray,
    projections: np.ndarray,
    available: np.ndarray,
    positions: np.ndarray,
    ros_points: np.ndarray,
    target: int = 15,
    worlds: int = 1000,
) -> tuple[list[int], set[int], list[int], list[int]]:
    """Drop minimum-cost extras or add maximum-gain free agents."""
    roster = list(roster)
    free_agents = set(free_agents)
    dropped = []
    added = []
    while len(roster) > target:
        full = roster_welp(points, projections, available, positions, roster, worlds)
        costs = [
            full - roster_welp(
                points, projections, available, positions,
                [candidate for candidate in roster if candidate != player], worlds,
            )
            for player in roster
        ]
        player = roster[int(np.argmin(costs))]
        roster.remove(player)
        free_agents.add(player)
        dropped.append(player)
    while len(roster) < target:
        candidates = []
        for position in np.unique(positions):
            eligible = [player for player in free_agents if positions[player] == position]
            candidates.extend(sorted(eligible, key=lambda player: ros_points[player], reverse=True)[:5])
        if not candidates:
            raise RuntimeError("no free agent available to fill roster")
        base = roster_welp(points, projections, available, positions, roster, worlds)
        gains = [
            roster_welp(points, projections, available, positions, roster + [player], worlds) - base
            for player in candidates
        ]
        player = candidates[int(np.argmax(gains))]
        roster.append(player)
        free_agents.remove(player)
        added.append(player)
    return roster, free_agents, dropped, added


def apply_trade(
    rosters: list[list[int]],
    free_agents: list[int],
    my_team: int,
    other_team: int,
    give: list[int],
    get: list[int],
    points: np.ndarray,
    projections: np.ndarray,
    available: np.ndarray,
    positions: np.ndarray,
    ros_points: np.ndarray,
    worlds: int = 1000,
) -> tuple[list[list[int]], dict]:
    """Apply and roster-balance a two-team trade."""
    updated = [list(roster) for roster in rosters]
    for player in give:
        updated[my_team].remove(player)
        updated[other_team].append(player)
    for player in get:
        updated[other_team].remove(player)
        updated[my_team].append(player)
    pool = set(free_agents)
    adjustments = {}
    for team in (my_team, other_team):
        updated[team], pool, dropped, added = rebalance_roster(
            updated[team], pool, points, projections, available, positions,
            ros_points, worlds=worlds,
        )
        adjustments[team] = {"dropped": dropped, "added": added}
    return updated, adjustments


def metric_delta(before: np.ndarray, after: np.ndarray) -> dict[str, float]:
    """Summarize paired common-random-number differences."""
    difference = np.asarray(after, dtype=float) - np.asarray(before, dtype=float)
    mean = float(difference.mean())
    se = float(difference.std(ddof=1) / np.sqrt(difference.size)) if difference.size > 1 else 0.0
    return {"mean": mean, "se": se, "low": mean - 1.645 * se, "high": mean + 1.645 * se}


def trade_verdict(interval: dict[str, float]) -> str:
    """Classify a paired trade effect interval."""
    if interval["low"] > 0:
        return "ACCEPT"
    if interval["high"] < 0:
        return "DECLINE"
    return "NO CLEAR EFFECT"


def evaluate_rosters(
    points, projections, available, positions, rosters, weeks, regular_end, playoff_teams
):
    """Run the shared-world season evaluator for a roster set."""
    return simulate_season(
        points, projections, available, positions, rosters, weeks, regular_end, playoff_teams
    )
