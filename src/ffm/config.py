from pathlib import Path

import yaml


def load_config(path: str | Path | None = None) -> dict:
    """Load the project YAML configuration."""
    config_path = Path(path) if path else Path(__file__).parents[2] / "config.yaml"
    with config_path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)
