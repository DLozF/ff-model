from pathlib import Path

from ffm.config import load_config


def test_load_config_reads_project_yaml():
    config = load_config(Path(__file__).parents[1] / "config.yaml")

    assert config["league"]["teams"] == 12
    assert config["sim"]["seed"] == 2026
