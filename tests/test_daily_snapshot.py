from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

import polars as pl
import yaml

from scripts.daily_snapshot import (
    create_daily_snapshot,
    finalize_snapshot,
    run_daily_snapshot,
    update_forward_report,
)


def test_create_daily_snapshot_records_model_and_market_ranks(tmp_path):
    players = pl.DataFrame({
        "player_id": ["a", "b", "c"],
        "name": ["Alpha", "Beta", "Gamma"],
        "position": ["RB", "RB", "WR"],
        "ros_points": [20.0, 10.0, 30.0],
    })
    market = pl.DataFrame({
        "sleeper_id": ["a", "b", "c"],
        "market_value": [100.0, 200.0, 300.0],
        "market_position_rank": [2, 1, 1],
    })
    captured_at = datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc)

    path = create_daily_snapshot(
        players, market, tmp_path, captured_at, season=2026, target_week=7
    )

    assert path.name == "model_vs_market_2026-10-20_153000Z.parquet"
    rows = pl.read_parquet(path).sort("sleeper_id")
    assert rows.select(
        "sleeper_id", "season", "target_week", "model_rank", "market_position_rank"
    ).to_dicts() == [
        {"sleeper_id": "a", "season": 2026, "target_week": 7, "model_rank": 1, "market_position_rank": 2},
        {"sleeper_id": "b", "season": 2026, "target_week": 7, "model_rank": 2, "market_position_rank": 1},
        {"sleeper_id": "c", "season": 2026, "target_week": 7, "model_rank": 1, "market_position_rank": 1},
    ]
    assert rows.get_column("actual_points").null_count() == 3


def test_create_daily_snapshot_reuses_existing_snapshot_for_central_day(tmp_path):
    players = pl.DataFrame({
        "player_id": ["a"], "name": ["Alpha"], "position": ["RB"], "ros_points": [20.0]
    })
    market = pl.DataFrame({
        "sleeper_id": ["a"], "market_value": [100.0], "market_position_rank": [1]
    })
    first = create_daily_snapshot(
        players,
        market,
        tmp_path,
        datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc),
        season=2026,
        target_week=7,
    )

    second = create_daily_snapshot(
        players,
        market,
        tmp_path,
        datetime(2026, 10, 20, 20, 45, tzinfo=timezone.utc),
        season=2026,
        target_week=7,
    )

    assert second == first
    assert len(list(tmp_path.glob("*.parquet"))) == 1


def test_finalize_snapshot_adds_actuals_and_scores_rank_accuracy(tmp_path):
    players = pl.DataFrame({
        "player_id": ["a", "b", "c"],
        "name": ["Alpha", "Beta", "Gamma"],
        "position": ["RB", "RB", "WR"],
        "ros_points": [20.0, 10.0, 30.0],
    })
    market = pl.DataFrame({
        "sleeper_id": ["a", "b", "c"],
        "market_value": [100.0, 200.0, 300.0],
        "market_position_rank": [2, 1, 1],
    })
    path = create_daily_snapshot(
        players,
        market,
        tmp_path,
        datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc),
        season=2026,
        target_week=7,
    )
    actuals = pl.DataFrame({
        "season": [2026, 2026, 2026],
        "week": [7, 7, 7],
        "sleeper_id": ["a", "b", "c"],
        "act_pts": [15.0, 5.0, 9.0],
    })

    comparison = finalize_snapshot(path, actuals)

    rows = pl.read_parquet(path).sort("sleeper_id")
    assert rows.get_column("actual_points").to_list() == [15.0, 5.0, 9.0]
    assert rows.get_column("actual_rank").to_list() == [1.0, 2.0, 1.0]
    assert comparison.filter(pl.col("position") == "RB").row(0, named=True) == {
        "captured_at": datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc),
        "season": 2026,
        "week": 7,
        "position": "RB",
        "players": 2,
        "model_mae": 0.0,
        "market_mae": 1.0,
        "closer": "model",
    }


def test_update_forward_report_replaces_its_section_without_overwriting_other_content(tmp_path):
    report = tmp_path / "model_vs_market.md"
    report.write_text("# Model vs market\n\nExisting rank gaps.\n", encoding="utf-8")
    comparisons = pl.DataFrame({
        "captured_at": [datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc)],
        "season": [2026],
        "week": [7],
        "position": ["RB"],
        "players": [2],
        "model_mae": [0.0],
        "market_mae": [1.0],
        "closer": ["model"],
    })

    update_forward_report(report, comparisons)
    update_forward_report(report, comparisons)

    text = report.read_text(encoding="utf-8")
    assert "Existing rank gaps." in text
    assert text.count("<!-- forward-test:start -->") == 1
    assert "| 2026-10-20 15:30 UTC | 2026 | 7 | RB | 2 | 0.000 | 1.000 | model |" in text


def test_run_daily_snapshot_uses_existing_market_cache_without_fetch(tmp_path, monkeypatch):
    cache = tmp_path / "data/cache"
    worlds = tmp_path / "worlds/2026_w2"
    cache.mkdir(parents=True)
    worlds.mkdir(parents=True)
    (tmp_path / "models").mkdir()
    (tmp_path / "reports").mkdir()
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"sim": {"current_season": 2026}}), encoding="utf-8"
    )
    (tmp_path / "models/world_manifest.json").write_text(
        json.dumps({"world_dir": str(worlds), "first_week": 2}), encoding="utf-8"
    )
    pl.DataFrame({
        "player_id": ["a"], "name": ["Alpha"], "position": ["RB"], "ros_points": [20.0]
    }).write_parquet(worlds / "player_index.parquet")
    pl.DataFrame({
        "season": [2026, 2026],
        "week": [1, 2],
        "game_type": ["REG", "REG"],
        "home_score": [20, None],
        "away_score": [17, None],
    }).write_parquet(cache / "nflverse_schedules.parquet")
    pl.DataFrame({
        "season": [2026], "week": [1], "sleeper_id": ["a"], "act_pts": [10.0]
    }).write_parquet(cache / "player_weeks.parquet")
    pl.DataFrame({
        "fetched_at": [datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc)],
        "redraftValue": [100.0],
        "trend30Day": [5.0],
        "overallRank": [1],
        "positionRank": [1],
        "player_sleeperId": ["a"],
        "player_name": ["Alpha"],
        "player_position": ["RB"],
        "player_team": ["AAA"],
    }).write_parquet(cache / "fantasycalc_values_2026-10-20.parquet")
    monkeypatch.setattr(
        "ffm.market.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected fetch")),
    )

    snapshot = run_daily_snapshot(
        tmp_path, datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc)
    )

    rows = pl.read_parquet(snapshot)
    assert rows.get_column("target_week").unique().to_list() == [2]
    assert rows.get_column("market_value").to_list() == [100.0]
    assert "No completed snapshots yet" in (tmp_path / "reports/model_vs_market.md").read_text()


def test_daily_snapshot_script_can_import_project_package_without_pythonpath():
    root = Path(__file__).parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy; runpy.run_path('scripts/daily_snapshot.py', run_name='not_main')",
        ],
        cwd=root,
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
