import numpy as np

from ffm.season import simulate_season


def test_season_invariants_and_reproducibility():
    rng = np.random.default_rng(2026)
    worlds, weeks, teams, roster_size = 100, 12, 12, 15
    players = teams * roster_size
    points = rng.uniform(0, 30, size=(weeks, worlds, players)).astype(np.float32)
    projections = np.broadcast_to(points.mean(axis=1)[:, None, :], points.shape).copy()
    available = np.ones_like(points, dtype=bool)
    positions = np.tile(np.array(["QB", "RB", "RB", "WR", "WR", "TE", "RB", "K", "DEF", "RB", "WR", "TE", "QB", "WR", "RB"]), teams)
    rosters = [list(range(team * roster_size, (team + 1) * roster_size)) for team in range(teams)]
    week_numbers = list(range(6, 18))

    first = simulate_season(points, projections, available, positions, rosters, week_numbers, 14, 6)
    second = simulate_season(points, projections, available, positions, rosters, week_numbers, 14, 6)

    assert abs(first["playoff_probability"].sum() - 6) < 1e-9
    assert abs(first["champion_probability"].sum() - 1) < 1e-9
    assert np.array_equal(first["champion"], second["champion"])
