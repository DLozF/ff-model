import numpy as np

from ffm.season import roster_team_scores, simulate_season, simulate_team_scores


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


def test_cached_team_scores_match_full_season_simulation():
    rng = np.random.default_rng(7)
    weeks, worlds, teams, roster_size = 12, 20, 12, 15
    players = teams * roster_size
    points = rng.uniform(0, 30, size=(weeks, worlds, players)).astype(np.float32)
    projections = np.broadcast_to(points.mean(axis=1)[:, None, :], points.shape).copy()
    available = np.ones_like(points, dtype=bool)
    positions = np.tile(np.array(["QB", "RB", "RB", "WR", "WR", "TE", "RB", "K", "DEF", "RB", "WR", "TE", "QB", "WR", "RB"]), teams)
    rosters = [list(range(team * roster_size, (team + 1) * roster_size)) for team in range(teams)]
    week_numbers = list(range(6, 18))

    scores = np.stack([
        roster_team_scores(points, projections, available, positions, roster)
        for roster in rosters
    ], axis=2)
    cached = simulate_team_scores(scores, week_numbers, 14, 6)
    full = simulate_season(points, projections, available, positions, rosters, week_numbers, 14, 6)

    assert np.array_equal(cached["playoff"], full["playoff"])
    assert np.array_equal(cached["champion"], full["champion"])


def test_playoff_reseeding_sends_lowest_remaining_seed_to_top_seed():
    scores = np.zeros((3, 1, 6), dtype=np.float32)
    scores[0, 0] = [0, 0, 10, 20, 10, 20]  # seeds 6 and 4 advance
    scores[1, 0] = [100, 90, 0, 0, 0, 95]  # seed 1 beats 6; seed 2 beats 4
    scores[2, 0] = [90, 100, 0, 0, 0, 80]  # seed 2 wins title

    result = simulate_team_scores(scores, [15, 16, 17], 14, 6, playoff_reseeding=True)

    assert result["champion"].tolist() == [1]
