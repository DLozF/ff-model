import polars as pl

from ffm.expected_bonus import expected_milestone_bonus, prior_rows


def test_projected_95_receiving_yards_has_bounded_expected_milestone_bonus():
    history_projection = [80.0, 90.0, 100.0, 110.0]
    history_actual = [85.0, 105.0, 120.0, 95.0]
    milestones = [
        {"threshold": 100, "points": 1.0},
        {"threshold": 150, "points": 2.0},
        {"threshold": 200, "points": 3.0},
    ]

    bonus = expected_milestone_bonus(
        95.0, history_projection, history_actual, milestones, mode="highest", k=4
    )

    assert 0.0 < bonus < 3.0


def test_prior_rows_never_include_target_week():
    frame = pl.DataFrame({
        "season": [2025, 2026, 2026, 2026],
        "week": [18, 1, 2, 3],
        "value": [1, 2, 3, 4],
    })

    history = prior_rows(frame, 2026, 2)

    assert history.get_column("value").to_list() == [1, 2]
    assert history.filter((pl.col("season") == 2026) & (pl.col("week") >= 2)).is_empty()
