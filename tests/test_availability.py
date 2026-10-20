import polars as pl

from ffm.availability import (
    DEFAULTS,
    estimate_markov,
    injury_status_outcomes,
    status_play_probabilities,
)


def test_defense_availability_never_misses_non_bye_week():
    assert DEFAULTS["h"]["DEF"] == 0.0


def test_markov_counts_transitions_inside_player_window():
    frame = pl.DataFrame({
        "season": [2025] * 4, "week": [1, 2, 3, 4], "sleeper_id": ["1"] * 4,
        "pos": ["RB"] * 4, "team": ["SEA"] * 4, "proj_pts": [10.0] * 4,
        "played": [True, False, False, True],
    })
    result = estimate_markov(frame, bye_weeks=set(), positions=["RB"])

    assert result["RB"]["h"] == 1.0
    assert result["RB"]["r"] == 0.5
    assert result["RB"]["h_n"] == 1
    assert result["RB"]["r_n"] == 2


def test_markov_treats_missing_middle_week_as_missed():
    frame = pl.DataFrame({
        "season": [2025, 2025], "week": [1, 3], "sleeper_id": ["1", "1"],
        "pos": ["RB", "RB"], "team": ["SEA", "SEA"], "proj_pts": [10.0, 10.0],
        "played": [True, True],
    })

    result = estimate_markov(frame, bye_weeks=set(), positions=["RB"])

    assert result["RB"]["h"] == 1.0
    assert result["RB"]["r"] == 1.0
    assert result["RB"]["h_n"] == 1
    assert result["RB"]["r_n"] == 1


def test_status_probabilities_match_played_rows():
    rows = pl.DataFrame({
        "report_status": ["Out", "Out", "Questionable", None],
        "played": [False, False, True, True],
    })
    result = status_play_probabilities(rows)

    assert result["Out"]["probability"] == 0
    assert result["Questionable"]["probability"] == 1
    assert result["none"]["probability"] == 1


def test_injury_status_outcomes_keeps_out_player_missing_from_projections():
    player_weeks = pl.DataFrame({
        "season": [2025], "week": [1], "gsis_id": ["g2"], "pos": ["WR"],
        "played": [True],
    })
    injuries = pl.DataFrame({
        "season": [2025, 2025], "week": [1, 1], "gsis_id": ["g1", "g2"],
        "position": ["RB", "WR"], "report_status": ["Out", "Questionable"],
        "date_modified": [1, 1],
    })
    stats = pl.DataFrame({"season": [2025], "week": [1], "player_id": ["g2"]}).with_columns(
        pl.col("season").cast(pl.Int32), pl.col("week").cast(pl.Int32)
    )
    snaps = pl.DataFrame(schema={
        "season": pl.Int64, "week": pl.Int64, "pfr_player_id": pl.String,
        "offense_snaps": pl.Float64, "defense_snaps": pl.Float64, "st_snaps": pl.Float64,
    })
    ids = pl.DataFrame(schema={"pfr_id": pl.String, "gsis_id": pl.String})

    rows = injury_status_outcomes(player_weeks, injuries, stats, snaps, ids)
    result = status_play_probabilities(rows)

    assert result["Out"] == {"probability": 0.0, "n": 1}
    assert result["Questionable"] == {"probability": 1.0, "n": 1}
