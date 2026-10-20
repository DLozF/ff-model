import numpy as np

from ffm.worlds import (
    apply_initial_overrides,
    load_injury_overrides,
    load_world_directory,
    weighted_recent_projection,
    write_world_manifest,
)


def test_weighted_recent_projection_uses_321_weights():
    assert weighted_recent_projection([6.0, 12.0, 18.0]) == 10.0
    assert weighted_recent_projection([12.0, 18.0]) == 14.0
    assert weighted_recent_projection([18.0]) == 18.0


def test_world_manifest_round_trip(tmp_path):
    manifest = tmp_path / "manifest.json"
    world_dir = tmp_path / "2026_w7"

    write_world_manifest(manifest, world_dir, first_week=7)

    assert load_world_directory(manifest) == world_dir


def test_override_with_tbd_weeks_changes_nothing():
    probabilities = np.array([0.8, 0.6])
    overrides = [{
        "name": "Jalen Hurts", "status": "out", "weeks": "TBD", "note": "blood clot",
    }]

    adjusted, weeks_out, pending = apply_initial_overrides(
        probabilities, np.array(["Jalen Hurts", "Other Player"]), overrides,
    )

    np.testing.assert_array_equal(adjusted, probabilities)
    np.testing.assert_array_equal(weeks_out, np.zeros(2, dtype=int))
    assert pending == overrides


def test_load_injury_overrides_accepts_top_level_list(tmp_path):
    path = tmp_path / "overrides.yaml"
    path.write_text("- name: Player One\n  P(play): 0.25\n", encoding="utf-8")

    assert load_injury_overrides(path) == [{"name": "Player One", "P(play)": 0.25}]
