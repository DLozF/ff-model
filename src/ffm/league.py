import numpy as np
import polars as pl
from pathlib import Path

BASE_NEEDS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1}


def _draft_values(players: pl.DataFrame) -> np.ndarray:
    return players.get_column("market_value").fill_null(0.0).to_numpy()


def _starter_slot(position: str, counts: dict[str, int], flex: int) -> str | None:
    if counts.get(position, 0) < BASE_NEEDS.get(position, 0):
        return position
    if position in {"RB", "WR", "TE"} and flex < 1:
        return "FLEX"
    return None


def synthetic_draft(players: pl.DataFrame, teams: int = 12, roster_size: int = 15) -> dict:
    """Snake-draft a synthetic league by FantasyCalc market value."""
    positions = players.get_column("pos").to_numpy()
    values = _draft_values(players)
    ros = (
        players.get_column("ros_points").fill_null(0.0).to_numpy()
        if "ros_points" in players.columns else values
    )
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
                if position in {"K", "DEF"}:
                    specialists = np.flatnonzero(available & (positions == position))
                    choice = int(specialists[np.argmax(ros[specialists])])
                else:
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
        "market_values": values.tolist(),
    }


def partial_synthetic_league(
    players: pl.DataFrame,
    real_roster_ids: list[str],
    real_team_name: str,
    teams: int = 12,
    roster_size: int = 15,
) -> dict:
    """Keep one real roster and draft synthetic opponents from the remaining pool."""
    id_to_index = {
        str(player_id): index
        for index, player_id in enumerate(players.get_column("sleeper_id"))
    }
    missing = [player_id for player_id in real_roster_ids if str(player_id) not in id_to_index]
    if missing:
        raise ValueError(f"real roster players missing from simulation pool: {missing}")
    real_roster = [id_to_index[str(player_id)] for player_id in real_roster_ids]
    real_set = set(real_roster)
    remaining_indices = [index for index in range(players.height) if index not in real_set]
    drafted = synthetic_draft(
        players[remaining_indices], teams=teams - 1, roster_size=roster_size
    )
    opponent_rosters = [
        [remaining_indices[index] for index in roster]
        for roster in drafted["rosters"]
    ]
    opponent_free_agents = [remaining_indices[index] for index in drafted["free_agents"]]
    return {
        "teams": [real_team_name, *[f"Team {index}" for index in range(2, teams + 1)]],
        "rosters": [real_roster, *opponent_rosters],
        "free_agents": opponent_free_agents,
        "market_values": _draft_values(players).tolist(),
        "partial_import": True,
        "real_team_index": 0,
    }


def load_real_league(cache: str | Path, player_index: pl.DataFrame) -> dict:
    """Load normalized Yahoo rosters and current standings."""
    cache = Path(cache)
    teams = pl.read_parquet(cache / "yahoo_teams.parquet").sort("team_id")
    rosters = pl.read_parquet(cache / "yahoo_rosters.parquet")
    free_agents = pl.read_parquet(cache / "yahoo_free_agents.parquet")
    standings = pl.read_parquet(cache / "yahoo_standings.parquet")
    mapping = {
        str(row["sleeper_id"]): int(row["player_index"])
        for row in player_index.select("sleeper_id", "player_index").drop_nulls().iter_rows(named=True)
    }
    roster_lists = []
    for team_id in teams.get_column("team_id"):
        roster_lists.append([
            mapping[str(sleeper_id)]
            for sleeper_id in rosters.filter(pl.col("team_id") == team_id).get_column("sleeper_id")
            if sleeper_id is not None and str(sleeper_id) in mapping
        ])
    return {
        "teams": teams.get_column("team_name").to_list(),
        "rosters": roster_lists,
        "free_agents": [
            mapping[str(sleeper_id)] for sleeper_id in free_agents.get_column("sleeper_id")
            if sleeper_id is not None and str(sleeper_id) in mapping
        ],
        "standings": standings.sort("team_id").to_dicts(),
    }
