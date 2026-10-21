from datetime import datetime, timezone

import polars as pl
import pytest

from ffm.shadow import (
    adoption_status,
    first_kickoff_utc,
    overlay_snapshot_points,
    score_shadow_snapshot,
    shadow_snapshot_path,
    training_before,
    write_snapshot_before_kickoff,
    write_snapshot_once,
)
from scripts.shadow_job import candidate_snapshot_rows


def test_shadow_training_is_strictly_before_target_week():
    frame = pl.DataFrame({
        "season": [2026, 2026, 2026], "week": [6, 7, 8],
        "played": [True, True, True], "pos": ["WR"] * 3,
        "proj_pts": [10.0, 11.0, 12.0], "candidate": [9.0, 99.0, 999.0],
        "act_pts": [12.0, 13.0, 14.0],
    })

    rows = training_before(frame, "candidate", 2026, 7)

    assert rows.get_column("week").to_list() == [6]
    assert rows.get_column("proj_pts").to_list() == [9.0]


def test_first_kickoff_uses_eastern_schedule_time():
    schedules = pl.DataFrame({
        "season": [2026], "week": [7], "game_type": ["REG"],
        "gameday": ["2026-10-22"], "gametime": ["20:15"],
    })

    kickoff = first_kickoff_utc(schedules, 2026, 7)

    assert kickoff == datetime(2026, 10, 23, 0, 15, tzinfo=timezone.utc)


def test_write_snapshot_once_never_overwrites_existing_file(tmp_path):
    path = tmp_path / "2026_w07.parquet"
    first = pl.DataFrame({"value": [1]})
    second = pl.DataFrame({"value": [2]})

    assert write_snapshot_once(path, first) is True
    assert write_snapshot_once(path, second) is False
    assert pl.read_parquet(path).item(0, "value") == 1


def test_snapshot_write_refuses_at_kickoff(tmp_path):
    path = tmp_path / "2026_w7.parquet"
    kickoff = datetime(2026, 10, 23, 0, 15, tzinfo=timezone.utc)

    with pytest.raises(RuntimeError, match="deadline passed"):
        write_snapshot_before_kickoff(path, pl.DataFrame({"value": [1]}), kickoff, kickoff)

    assert not path.exists()


def test_shadow_snapshot_path_uses_requested_unpadded_week(tmp_path):
    assert shadow_snapshot_path(tmp_path, 2026, 7) == tmp_path / "data/shadow/2026_w7.parquet"


def test_prior_shadow_points_override_rebuilt_projection_history():
    history = pl.DataFrame({
        "season": [2026, 2026], "week": [7, 7],
        "sleeper_id": ["a", "b"], "proj_pts": [99.0, 88.0],
    })
    snapshot = pl.DataFrame({
        "season": [2026, 2026], "week": [7, 7],
        "sleeper_id": ["a", "b"], "candidate": ["sleeper", "sleeper"],
        "proj_pts": [10.0, 11.0],
    })

    restored = overlay_snapshot_points(history, snapshot, "sleeper", "proj_pts")

    assert restored.get_column("proj_pts").to_list() == [10.0, 11.0]


def test_shadow_scoring_reports_position_spearman_and_crps():
    rows = []
    for candidate, projections in {
        "sleeper": [1.0, 2.0, 3.0, 4.0],
        "def_stop": [1.1, 2.1, 3.1, 4.1],
        "expanded_ridge": [4.0, 3.0, 2.0, 1.0],
    }.items():
        for index, projection in enumerate(projections):
            rows.append({
                "season": 2026, "week": 7, "candidate": candidate,
                "sleeper_id": f"p{index}", "pos": "WR", "proj_pts": projection,
                "quantile_levels": [0.25, 0.5, 0.75],
                "quantiles": [projection - 1, projection, projection + 1],
            })
    snapshot = pl.from_dicts(rows)
    actuals = pl.DataFrame({
        "season": [2026] * 4, "week": [7] * 4,
        "sleeper_id": [f"p{i}" for i in range(4)], "act_pts": [1.0, 2.0, 3.0, 4.0],
        "played": [True] * 4,
    })

    position, weekly = score_shadow_snapshot(snapshot, actuals)

    assert position.filter(pl.col("candidate") == "sleeper").item(0, "spearman") == 1.0
    assert position.filter(pl.col("candidate") == "expanded_ridge").item(0, "spearman") == -1.0
    assert weekly.filter(pl.col("candidate") == "sleeper").item(0, "crps") >= 0.0


def test_adoption_requires_four_spearman_wins_and_crps_guard():
    rows = []
    for week in range(7, 13):
        rows.extend([
            {"week": week, "candidate": "sleeper", "spearman": 0.50, "crps": 4.0, "n": 100},
            {"week": week, "candidate": "def_stop", "spearman": 0.51 if week <= 10 else 0.49, "crps": 4.01, "n": 100},
            {"week": week, "candidate": "expanded_ridge", "spearman": 0.52, "crps": 4.03, "n": 100},
        ])

    status = adoption_status(pl.from_dicts(rows))

    assert status["def_stop"]["spearman_wins"] == 4
    assert status["def_stop"]["eligible"] is True
    assert status["expanded_ridge"]["eligible"] is False


def test_candidate_quantiles_refit_around_candidate_residuals():
    training = pl.DataFrame({
        "season": [2025] * 60, "week": [(index % 18) + 1 for index in range(60)],
        "sleeper_id": [f"p{index}" for index in range(60)], "pos": ["WR"] * 60,
        "played": [True] * 60, "act_pts": [10.0] * 60,
        "proj_pts": [10.0] * 60, "candidate": [15.0] * 60,
    })
    target = pl.DataFrame({
        "season": [2026], "week": [7], "sleeper_id": ["target"],
        "name": ["Target Player"], "pos": ["WR"], "team": ["TB"], "opp": ["CAR"],
        "candidate": [15.0],
    })

    snapshot = candidate_snapshot_rows(
        "candidate", training, target, "candidate",
        datetime(2026, 10, 21, tzinfo=timezone.utc),
        datetime(2026, 10, 23, tzinfo=timezone.utc),
    )
    levels = snapshot.item(0, "quantile_levels")
    quantiles = snapshot.item(0, "quantiles")
    median = quantiles[min(range(len(levels)), key=lambda index: abs(levels[index] - 0.5))]

    assert median < 12.0
    assert snapshot.item(0, "training_max_key") < 202607
