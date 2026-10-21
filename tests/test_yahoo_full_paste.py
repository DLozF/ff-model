from pathlib import Path

import polars as pl
import pytest

from scripts.parse_yahoo_paste import FullPasteError, build_full_paste_tables

FIXTURES = Path(__file__).parent / "fixtures"


def full_paste_dir(tmp_path):
    (tmp_path / "settings.txt").write_text((FIXTURES / "yahoo_settings_fake.txt").read_text())
    (tmp_path / "my_team.txt").write_text("Nebula Foxes\n")
    (tmp_path / "my_roster.txt").write_text((FIXTURES / "yahoo_roster_page_fake.txt").read_text())
    (tmp_path / "team_02.txt").write_text(
        "Team: Quantum Owls\nQB\tDelta ThrowerPlayer Note Bal - QB\n"
        "RB\tEpsilon RunnerPlayer Note Cle - RB\n"
    )
    (tmp_path / "standings.txt").write_text((FIXTURES / "yahoo_standings_full_fake.txt").read_text())
    (tmp_path / "schedule_w08.txt").write_text((FIXTURES / "yahoo_schedule_full_fake.txt").read_text())
    return tmp_path


def fake_players():
    return pl.DataFrame({
        "player_id": ["p1", "p2", "p3", "p4", "p5", "extra"],
        "full_name": ["Alpha Passer", "Beta Catcher", "Gamma Stash", "Delta Thrower", "Epsilon Runner", "Free Agent"],
        "position": ["QB", "WR", "WR", "QB", "RB", "TE"],
        "team": ["TB", "NE", "NO", "BAL", "CLE", "DAL"],
    })


def test_full_paste_tables_use_all_rosters_standings_and_schedule(tmp_path):
    tables, unparsed, unmatched = build_full_paste_tables(
        full_paste_dir(tmp_path), fake_players(), expected_teams=2
    )

    assert tables["teams"].height == 2
    assert tables["rosters"].get_column("team_id").n_unique() == 2
    assert tables["schedule"].height == 2
    assert tables["settings"]["partial_import"] is False
    assert unmatched == []
    assert any("This row is not a player" in line for line in unparsed)


def test_full_paste_stops_after_more_than_three_unmatched_players(tmp_path):
    empty_players = pl.DataFrame({
        "player_id": [], "full_name": [], "position": [], "team": [],
    }, schema={"player_id": pl.String, "full_name": pl.String, "position": pl.String, "team": pl.String})

    with pytest.raises(FullPasteError) as error:
        build_full_paste_tables(full_paste_dir(tmp_path), empty_players, expected_teams=2)

    assert len(error.value.needs_diego) > 3
