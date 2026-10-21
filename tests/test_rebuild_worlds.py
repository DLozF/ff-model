import json
from pathlib import Path

from scripts.rebuild_worlds import worlds_present
import scripts.rebuild_worlds as rebuild_worlds


def test_worlds_present_true_when_directory_exists(tmp_path, monkeypatch):
    manifest = tmp_path / "world_manifest.json"
    manifest.write_text(json.dumps({"world_dir": str(tmp_path / "worlds")}))
    (tmp_path / "worlds").mkdir()
    monkeypatch.setattr(rebuild_worlds, "MANIFEST", manifest)

    assert worlds_present() is True


def test_worlds_present_false_when_directory_is_missing(tmp_path, monkeypatch):
    manifest = tmp_path / "world_manifest.json"
    manifest.write_text(json.dumps({"world_dir": str(tmp_path / "missing")}))
    monkeypatch.setattr(rebuild_worlds, "MANIFEST", manifest)

    assert worlds_present() is False
