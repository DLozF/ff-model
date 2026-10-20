import polars as pl

from ffm.actuals import (
    merge_actual_sources,
    nflverse_actual_rows,
    projection_team_gaps,
    replace_season,
)
from ffm.config import load_config


def test_nflverse_actual_rows_maps_ids_and_scores():
    stats = pl.DataFrame({
        "season": [2026], "week": [6], "player_id": ["g1"], "position": ["QB"],
        "passing_yards": [250], "passing_tds": [2], "passing_interceptions": [1],
        "passing_2pt_conversions": [0], "rushing_yards": [20], "rushing_tds": [0],
        "rushing_2pt_conversions": [0], "receptions": [0], "receiving_yards": [0],
        "receiving_tds": [0], "receiving_2pt_conversions": [0],
        "fumbles_lost_total": [0], "special_teams_tds": [0], "pat_made": [0],
        "fg_made_0_19": [0], "fg_made_20_29": [0], "fg_made_30_39": [0],
        "fg_made_40_49": [0], "fg_made_50_59": [0], "fg_made_60_": [0],
    })
    ids = pl.DataFrame({"gsis_id": ["g1"], "sleeper_id": [123]})

    actuals = nflverse_actual_rows(stats, ids, load_config()["scoring"])

    assert actuals.row(0, named=True)["player_id"] == "123"
    assert actuals.row(0, named=True)["pts_ppr"] == 19.0
    assert actuals.row(0, named=True)["gp"] == 1.0


def test_projection_team_gaps_only_flags_completed_weeks():
    projections = pl.DataFrame({
        "season": [2026, 2026, 2026], "week": [1, 1, 2],
        "player_id": ["1", "2", "3"], "team": ["SEA", "SF", "SEA"],
    })
    actuals = pl.DataFrame({"season": [2026], "week": [1], "player_id": ["1"]})
    schedules = pl.DataFrame({
        "season": [2026, 2026], "week": [1, 1], "game_type": ["REG", "REG"],
        "home_team": ["SEA", "LAR"], "away_team": ["SF", "ARI"],
        "home_score": [20, 17], "away_score": [10, 14],
    })

    gaps = projection_team_gaps(projections, actuals, schedules)

    assert gaps.select("season", "week", "team").rows() == [(2026, 1, "SF")]
    assert gaps.get_column("scheduled_game").to_list() == [True]


def test_replace_season_keeps_other_seasons_and_refreshes_target():
    existing = pl.DataFrame({"season": [2025, 2026], "value": [1, 2]})
    fresh = pl.DataFrame({"season": [2026], "value": [3]})

    result = replace_season(existing, fresh, 2026)

    assert result.sort("season").rows() == [(2025, 1), (2026, 3)]


def test_nflverse_supplement_overrides_sleeper_actual():
    sleeper = pl.DataFrame({
        "season": [2026], "week": [6], "player_id": ["1"], "pts_ppr": [0.0]
    })
    nflverse = pl.DataFrame({
        "season": [2026], "week": [6], "player_id": ["1"], "pts_ppr": [20.0]
    })

    result = merge_actual_sources(sleeper, nflverse)

    assert result.get_column("pts_ppr").to_list() == [20.0]
