import numpy as np
import polars as pl

REPLACEMENT_RANK = {"QB": 12, "RB": 28, "WR": 28, "TE": 16, "K": 12, "DEF": 12}
BASE_NEEDS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1}


def _draft_values(players: pl.DataFrame) -> np.ndarray:
    positions = players.get_column("pos").to_numpy()
    points = players.get_column("ros_points").to_numpy()
    values = np.empty(players.height)
    for position in REPLACEMENT_RANK:
        indices = np.flatnonzero(positions == position)
        ordered = indices[np.argsort(points[indices])[::-1]]
        rank = min(REPLACEMENT_RANK[position] - 1, ordered.size - 1)
        replacement = points[ordered[rank]]
        values[indices] = points[indices] - replacement
    return values


def _starter_slot(position: str, counts: dict[str, int], flex: int) -> str | None:
    if counts.get(position, 0) < BASE_NEEDS.get(position, 0):
        return position
    if position in {"RB", "WR", "TE"} and flex < 1:
        return "FLEX"
    return None


def synthetic_draft(players: pl.DataFrame, teams: int = 12, roster_size: int = 15) -> dict:
    """Snake-draft a synthetic league by value over replacement."""
    positions = players.get_column("pos").to_numpy()
    values = _draft_values(players)
    order = np.argsort(values)[::-1]
    available = np.ones(players.height, dtype=bool)
    rosters = [[] for _ in range(teams)]
    counts = [dict() for _ in range(teams)]
    flex = [0 for _ in range(teams)]
    for round_index in range(roster_size):
        team_order = range(teams) if round_index % 2 == 0 else range(teams - 1, -1, -1)
        for team in team_order:
            choice = None
            chosen_slot = None
            for player in order:
                if not available[player]:
                    continue
                position = positions[player]
                if round_index < 9:
                    slot = _starter_slot(position, counts[team], flex[team])
                    if slot is None:
                        continue
                else:
                    if position in {"K", "DEF"}:
                        continue
                    slot = "BENCH"
                choice = int(player)
                chosen_slot = slot
                break
            if choice is None:
                raise RuntimeError(f"no legal player for Team {team + 1} round {round_index + 1}")
            available[choice] = False
            rosters[team].append(choice)
            if chosen_slot == "FLEX":
                flex[team] += 1
            elif chosen_slot != "BENCH":
                position = positions[choice]
                counts[team][position] = counts[team].get(position, 0) + 1
    return {
        "teams": [f"Team {index + 1}" for index in range(teams)],
        "rosters": rosters,
        "free_agents": np.flatnonzero(available).tolist(),
        "vor": values.tolist(),
    }
