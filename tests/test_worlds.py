import numpy as np

from ffm.worlds import load_world_directory, weighted_recent_projection, write_world_manifest


def test_weighted_recent_projection_uses_321_weights():
    assert weighted_recent_projection([6.0, 12.0, 18.0]) == 10.0
    assert weighted_recent_projection([12.0, 18.0]) == 14.0
    assert weighted_recent_projection([18.0]) == 18.0


def test_world_manifest_round_trip(tmp_path):
    manifest = tmp_path / "manifest.json"
    world_dir = tmp_path / "2026_w7"

    write_world_manifest(manifest, world_dir, first_week=7)

    assert load_world_directory(manifest) == world_dir
