import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1}
FLEX = {"RB", "WR", "TE"}


def _take_best(
    projections: np.ndarray,
    eligible: np.ndarray,
    available: np.ndarray,
    selected: np.ndarray,
) -> None:
    scores = np.where(eligible[None, :] & available & ~selected, projections, -np.inf)
    best = np.argmax(scores, axis=1)
    worlds = np.arange(projections.shape[0])
    valid = np.isfinite(scores[worlds, best])
    selected[worlds[valid], best[valid]] = True


def greedy(proj: np.ndarray, pos: np.ndarray, avail: np.ndarray) -> np.ndarray:
    """Choose optimal lineups for every world from projected points."""
    projections = np.asarray(proj, dtype=float)
    available = np.asarray(avail, dtype=bool)
    one_world = projections.ndim == 1
    if one_world:
        projections = projections[None, :]
        available = available[None, :]
    positions = np.asarray(pos)
    if projections.shape != available.shape or projections.shape[1] != positions.size:
        raise ValueError("proj, pos, and avail shapes do not align")
    selected = np.zeros_like(available)
    for position, count in STARTERS.items():
        eligible = positions == position
        for _ in range(count):
            _take_best(projections, eligible, available, selected)
    _take_best(projections, np.isin(positions, list(FLEX)), available, selected)
    return selected[0] if one_world else selected


def pulp_lineup(proj: np.ndarray, pos: np.ndarray, avail: np.ndarray) -> np.ndarray:
    """Solve one lineup as an integer program for test reference."""
    projections = np.asarray(proj, dtype=float)
    positions = np.asarray(pos)
    available = np.asarray(avail, dtype=bool)
    slots = ["QB", "RB1", "RB2", "WR1", "WR2", "TE", "K", "DEF", "FLEX"]
    eligible = {
        "QB": {"QB"}, "RB1": {"RB"}, "RB2": {"RB"},
        "WR1": {"WR"}, "WR2": {"WR"}, "TE": {"TE"},
        "K": {"K"}, "DEF": {"DEF"}, "FLEX": FLEX,
    }
    variables = [
        (index, slot)
        for index in range(positions.size)
        for slot in slots
        if available[index] and positions[index] in eligible[slot]
    ]
    rows = []
    for index in range(positions.size):
        rows.append([float(player == index) for player, _ in variables])
    for slot in slots:
        rows.append([float(role == slot) for _, role in variables])
    result = milp(
        c=-np.array([projections[index] for index, _ in variables]),
        integrality=np.ones(len(variables)),
        bounds=Bounds(0, 1),
        constraints=LinearConstraint(np.array(rows), 0, 1),
        options={"disp": False},
    )
    if not result.success:
        raise RuntimeError(f"lineup integer program failed: {result.message}")
    selected = np.zeros(positions.size, dtype=bool)
    for (index, _), value in zip(variables, result.x):
        selected[index] |= value > 0.5
    return selected
