import numpy as np

from ffm.lineup import greedy, pulp_lineup, risk_tiebreak


def test_greedy_handles_bye_injury_and_flex():
    pos = np.array(["QB", "QB", "RB", "RB", "RB", "WR", "WR", "WR", "TE", "TE", "K", "DEF"])
    proj = np.array([[20, 15, 18, 16, 14, 17, 13, 12, 11, 8, 9, 7]], dtype=float)
    avail = np.ones_like(proj, dtype=bool)
    avail[0, 0] = False
    avail[0, 2] = False

    selected = greedy(proj, pos, avail)

    assert selected[0, 1]
    assert not selected[0, 0]
    assert not selected[0, 2]
    assert selected[0, 3:5].all()
    assert selected[0, 5:8].all()
    assert selected[0, 8]
    assert not selected[0, 9]


def test_greedy_matches_pulp_on_1000_random_rosters():
    rng = np.random.default_rng(2026)
    pos = np.array(["QB"] * 3 + ["RB"] * 5 + ["WR"] * 6 + ["TE"] * 3 + ["K"] * 2 + ["DEF"] * 2)
    proj = rng.uniform(0, 30, size=(1000, pos.size))
    avail = rng.random(size=proj.shape) > 0.15

    selected = greedy(proj, pos, avail)
    greedy_totals = (selected * proj).sum(axis=1)
    pulp_totals = np.array([
        (pulp_lineup(proj[world], pos, avail[world]) * proj[world]).sum()
        for world in range(1000)
    ])

    assert np.max(np.abs(greedy_totals - pulp_totals)) < 1e-6


def test_risk_tiebreak_only_uses_variance_inside_half_point():
    assert risk_tiebreak(np.array([10.0, 9.4]), np.array([1.0, 9.0]), True) == 0
    assert risk_tiebreak(np.array([10.0, 9.6]), np.array([1.0, 9.0]), True) == 1
    assert risk_tiebreak(np.array([10.0, 9.6]), np.array([1.0, 9.0]), False) == 0
