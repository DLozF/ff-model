import numpy as np
from scipy.stats import norm


def weighted_recent_projection(values: list[float]) -> float:
    """Return a 3:2:1 weighted average from newest-first values."""
    recent = list(values)[:3]
    weights = list(range(len(recent), 0, -1))
    return sum(value * weight for value, weight in zip(recent, weights)) / sum(weights)


def _initial_probabilities(positions, statuses, availability):
    status_prob = availability["status_play_probability"]
    probabilities = np.empty(len(positions), dtype=float)
    for index, status in enumerate(statuses):
        label = status if status in status_prob else "none"
        if status in {"IR", "PUP"}:
            probabilities[index] = availability["r_ir"]["value"]
        else:
            probabilities[index] = status_prob[label]["probability"]
    return probabilities


def _slot_players(team, positions, teams, projections):
    slots = [[] for _ in range(9)]
    team_indices = np.flatnonzero(teams == team)
    qbs = team_indices[positions[team_indices] == "QB"]
    slots[0] = qbs.tolist()
    plans = (("RB", 2, 1), ("WR", 3, 3), ("TE", 1, 6), ("K", 1, 7), ("DEF", 1, 8))
    for position, count, offset in plans:
        eligible = team_indices[positions[team_indices] == position]
        if eligible.size:
            ordered = eligible[np.argsort(projections[eligible])[::-1]]
            for rank, player in enumerate(ordered[:count]):
                slots[offset + rank] = [int(player)]
    return slots


def _correlated_normals(rng, worlds, positions, teams, projections, games, factor):
    latent = rng.standard_normal((worlds, positions.size))
    for home, away in games:
        draw = rng.standard_normal((worlds, 18)) @ factor.T
        for offset, team in ((0, home), (9, away)):
            slots = _slot_players(team, positions, teams, projections)
            for slot, players in enumerate(slots):
                if players:
                    latent[:, players] = draw[:, [offset + slot]]
    return latent


def _adjust_for_backup_qbs(proj_seen, available, base, positions, teams, qb_effect):
    kappa = qb_effect["kappa"]
    betas = {position: values["value"] for position, values in qb_effect["beta"].items()}
    worlds = proj_seen.shape[0]
    rows = np.arange(worlds)
    for team in sorted({team for team in teams if team is not None}):
        qbs = np.flatnonzero((teams == team) & (positions == "QB"))
        if not qbs.size:
            continue
        qbs = qbs[np.argsort(base[qbs])[::-1]]
        qb_available = available[:, qbs]
        any_qb = qb_available.any(axis=1)
        first = np.argmax(qb_available, axis=1)
        chosen = qbs[first]
        backup = any_qb & (chosen != qbs[0])
        if np.any(backup):
            backup_rows = rows[backup]
            proj_seen[backup_rows, chosen[backup]] = kappa * base[qbs[0]]
            for position, beta in betas.items():
                skill = np.flatnonzero((teams == team) & (positions == position))
                proj_seen[np.ix_(backup_rows, skill)] *= 1 - beta * (1 - kappa)
    return proj_seen


def generate_worlds(
    projections: np.ndarray,
    bye: np.ndarray,
    positions: np.ndarray,
    teams: np.ndarray,
    injury_status: np.ndarray,
    games: list[list[tuple[str, str]]],
    model,
    availability: dict,
    qb_effect: dict,
    sigma: np.ndarray,
    n_worlds: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate correlated points, availability, and seen projections."""
    rng = np.random.default_rng(seed)
    weeks, players = projections.shape
    points = np.empty((weeks, n_worlds, players), dtype=np.float32)
    available_output = np.empty((weeks, n_worlds, players), dtype=bool)
    seen_output = np.empty((weeks, n_worlds, players), dtype=np.float32)
    initial = _initial_probabilities(positions, injury_status, availability)
    health = rng.random((n_worlds, players)) < initial
    h = np.array([availability["markov"][position]["h"] for position in positions])
    r = np.array([availability["markov"][position]["r"] for position in positions])
    factor = np.linalg.cholesky(sigma)
    for week in range(weeks):
        if week:
            draws = rng.random((n_worlds, players))
            health = np.where(health, draws >= h, draws < r)
        available = health & ~bye[week][None, :]
        proj_seen = np.broadcast_to(projections[week], (n_worlds, players)).copy()
        proj_seen = _adjust_for_backup_qbs(
            proj_seen, available, projections[week], positions, teams, qb_effect
        )
        latent = _correlated_normals(
            rng, n_worlds, positions, teams, projections[week], games[week], factor
        )
        uniforms = norm.cdf(latent)
        week_points = np.zeros((n_worlds, players), dtype=np.float32)
        for position in model.tables:
            indices = np.flatnonzero(positions == position)
            if indices.size:
                week_points[:, indices] = model.ppf(
                    position, proj_seen[:, indices], uniforms[:, indices]
                ).astype(np.float32)
        points[week] = week_points * available
        available_output[week] = available
        seen_output[week] = proj_seen
    return points, available_output, seen_output
