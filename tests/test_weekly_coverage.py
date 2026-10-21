import numpy as np
import polars as pl

from ffm.coverage import latest_coverage_lines, weekly_position_coverage


class FixedIntervalModel:
    levels = np.array([0.10, 0.90])
    tables = {"QB": object(), "RB": object()}

    def quantile_matrix(self, position, projection):
        projection = np.asarray(projection, dtype=float)
        return np.column_stack([projection - 2.0, projection + 2.0])


def test_weekly_position_coverage_uses_only_played_rows():
    player_weeks = pl.DataFrame({
        "season": [2026, 2026, 2026, 2026, 2026],
        "week": [1, 1, 1, 2, 2],
        "pos": ["QB", "QB", "RB", "QB", "QB"],
        "proj_pts": [10.0, 10.0, 8.0, 12.0, 12.0],
        "act_pts": [11.0, 20.0, 7.0, 13.0, 30.0],
        "played": [True, True, False, True, True],
    })

    result = weekly_position_coverage(player_weeks, FixedIntervalModel(), 2026)

    assert result.sort("week").select("week", "position", "players", "coverage").to_dicts() == [
        {"week": 1, "position": "QB", "players": 2, "coverage": 0.5},
        {"week": 2, "position": "QB", "players": 2, "coverage": 0.5},
    ]


def test_latest_coverage_lines_emit_one_line_per_position():
    coverage = pl.DataFrame({
        "season": [2026, 2026],
        "week": [6, 6],
        "position": ["QB", "RB"],
        "players": [25, 40],
        "nominal": [0.8, 0.8],
        "coverage": [0.72, 0.80],
    })

    lines = latest_coverage_lines(coverage)

    assert len(lines) == 6
    assert lines[0] == "- Week 6 QB 80% coverage: 72.0% (n=25)."
    assert lines[1] == "- Week 6 RB 80% coverage: 80.0% (n=40)."
    assert lines[-1] == "- Week 6 DEF 80% coverage: no played players."
