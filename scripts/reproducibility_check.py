#!/usr/bin/env python3
"""Run a small same-seed P6 season reproducibility probe."""

import hashlib

import numpy as np

from ffm.season import simulate_season


POSITIONS = np.array(
    ["QB", "RB", "RB", "WR", "WR", "TE", "RB", "K", "DEF", "RB", "WR", "TE", "QB", "WR", "RB"]
)


def run_once(seed: int) -> tuple[str, dict[str, np.ndarray]]:
    """Run a deterministic miniature season and return its digest and arrays."""
    rng = np.random.default_rng(seed)
    worlds, weeks, teams, roster_size = 64, 12, 12, len(POSITIONS)
    players = teams * roster_size
    points = rng.uniform(0, 30, size=(weeks, worlds, players)).astype(np.float32)
    projections = np.broadcast_to(points.mean(axis=1)[:, None, :], points.shape).copy()
    available = rng.random(points.shape) >= 0.08
    positions = np.tile(POSITIONS, teams)
    rosters = [
        list(range(team * roster_size, (team + 1) * roster_size))
        for team in range(teams)
    ]
    result = simulate_season(
        points,
        projections,
        available,
        positions,
        rosters,
        list(range(6, 18)),
        regular_season_end=14,
        playoff_teams=6,
    )
    arrays = {key: value for key, value in result.items() if isinstance(value, np.ndarray)}
    digest = hashlib.sha256()
    for key in sorted(arrays):
        value = np.ascontiguousarray(arrays[key])
        digest.update(key.encode("utf-8"))
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest(), arrays


def main() -> None:
    """Fail unless two independent same-seed runs are byte-identical."""
    first_digest, first = run_once(2026)
    second_digest, second = run_once(2026)
    if first_digest != second_digest or any(
        not np.array_equal(first[key], second[key]) for key in first
    ):
        raise SystemExit("reproducibility check failed")
    print(f"reproducibility check passed: {first_digest}")


if __name__ == "__main__":
    main()
