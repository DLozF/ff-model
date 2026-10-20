import numpy as np

from ffm.lineup import greedy


def round_robin(teams: int) -> list[list[tuple[int, int]]]:
    """Generate a single round-robin schedule."""
    rotation = list(range(teams))
    rounds = []
    for _ in range(teams - 1):
        rounds.append([(rotation[i], rotation[-1 - i]) for i in range(teams // 2)])
        rotation = [rotation[0], rotation[-1], *rotation[1:-1]]
    return rounds


def roster_team_scores(points, projections, available, positions, roster):
    """Return week-by-world scores for one roster."""
    indices = np.asarray(roster)
    scores = np.zeros(points.shape[:2], dtype=np.float32)
    for week in range(points.shape[0]):
        selected = greedy(
            projections[week][:, indices], positions[indices], available[week][:, indices]
        )
        scores[week] = np.sum(points[week][:, indices] * selected, axis=1)
    return scores


def _team_scores(points, projections, available, positions, rosters):
    return np.stack([
        roster_team_scores(points, projections, available, positions, roster)
        for roster in rosters
    ], axis=2)


def _scores_for(scores: np.ndarray, teams: np.ndarray) -> np.ndarray:
    worlds = np.arange(scores.shape[0])
    return scores[worlds, teams]


def _winner(scores: np.ndarray, high_seed: np.ndarray, low_seed: np.ndarray) -> np.ndarray:
    high_score = _scores_for(scores, high_seed)
    low_score = _scores_for(scores, low_seed)
    return np.where(high_score >= low_score, high_seed, low_seed)


def simulate_team_scores(
    team_scores: np.ndarray,
    week_numbers: list[int],
    regular_season_end: int,
    playoff_teams: int,
    playoff_reseeding: bool = False,
) -> dict:
    """Simulate standings and playoffs from cached team scores."""
    worlds = team_scores.shape[1]
    teams = team_scores.shape[2]
    wins = np.zeros((worlds, teams), dtype=np.float32)
    points_for = np.zeros((worlds, teams), dtype=np.float32)
    schedule = round_robin(teams)
    regular_indices = [i for i, week in enumerate(week_numbers) if week <= regular_season_end]
    for round_index, week_index in enumerate(regular_indices):
        scores = team_scores[week_index]
        points_for += scores
        for left, right in schedule[round_index % len(schedule)]:
            wins[:, left] += (scores[:, left] > scores[:, right]) + 0.5 * (scores[:, left] == scores[:, right])
            wins[:, right] += (scores[:, right] > scores[:, left]) + 0.5 * (scores[:, left] == scores[:, right])
    team_key = np.broadcast_to(np.arange(teams), wins.shape)
    seeds = np.lexsort((team_key, -points_for, -wins), axis=1)
    playoff = np.zeros((worlds, teams), dtype=bool)
    np.put_along_axis(playoff, seeds[:, :playoff_teams], True, axis=1)
    bye = np.zeros_like(playoff)
    np.put_along_axis(bye, seeds[:, :2], True, axis=1)

    week15 = team_scores[week_numbers.index(15)]
    week16 = team_scores[week_numbers.index(16)]
    week17 = team_scores[week_numbers.index(17)]
    seed_teams = seeds[:, :6]
    winner_36 = _winner(week15, seed_teams[:, 2], seed_teams[:, 5])
    winner_45 = _winner(week15, seed_teams[:, 3], seed_teams[:, 4])
    if playoff_reseeding:
        seed_rank = np.empty_like(seeds)
        np.put_along_axis(seed_rank, seeds, np.arange(teams)[None, :], axis=1)
        winner_36_is_lower = _scores_for(seed_rank, winner_36) > _scores_for(seed_rank, winner_45)
        low_remaining = np.where(winner_36_is_lower, winner_36, winner_45)
        high_remaining = np.where(winner_36_is_lower, winner_45, winner_36)
        finalist_1 = _winner(week16, seed_teams[:, 0], low_remaining)
        finalist_2 = _winner(week16, seed_teams[:, 1], high_remaining)
    else:
        finalist_1 = _winner(week16, seed_teams[:, 0], winner_45)
        finalist_2 = _winner(week16, seed_teams[:, 1], winner_36)
    champion = _winner(week17, finalist_1, finalist_2)
    champion_flags = np.zeros((worlds, teams), dtype=bool)
    champion_flags[np.arange(worlds), champion] = True
    return {
        "playoff": playoff,
        "bye": bye,
        "champion": champion,
        "champion_flags": champion_flags,
        "wins": wins,
        "points_for": points_for,
        "team_week_scores": team_scores,
        "playoff_probability": playoff.mean(axis=0),
        "bye_probability": bye.mean(axis=0),
        "champion_probability": champion_flags.mean(axis=0),
        "expected_wins": wins.mean(axis=0),
        "expected_points_for": points_for.mean(axis=0),
    }


def simulate_season(
    points: np.ndarray,
    projections: np.ndarray,
    available: np.ndarray,
    positions: np.ndarray,
    rosters: list[list[int]],
    week_numbers: list[int],
    regular_season_end: int,
    playoff_teams: int,
    playoff_reseeding: bool = False,
) -> dict:
    """Simulate standings and a six-team, three-week playoff bracket."""
    return simulate_team_scores(
        _team_scores(points, projections, available, positions, rosters),
        week_numbers, regular_season_end, playoff_teams, playoff_reseeding,
    )
