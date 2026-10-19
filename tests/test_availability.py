import polars as pl

from ffm.availability import estimate_markov, status_play_probabilities


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


def test_status_probabilities_match_played_rows():
    rows = pl.DataFrame({
        "report_status": ["Out", "Out", "Questionable", None],
        "played": [False, False, True, True],
    })
    result = status_play_probabilities(rows)

    assert result["Out"]["probability"] == 0
    assert result["Questionable"]["probability"] == 1
    assert result["none"]["probability"] == 1
