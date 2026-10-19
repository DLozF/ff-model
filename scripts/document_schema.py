from pathlib import Path

import polars as pl

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"
DATASETS = {
    "Sleeper projections": CACHE / "sleeper_projections_2025_w05.parquet",
    "Sleeper stats": CACHE / "sleeper_stats_2025_w05.parquet",
    "Sleeper players": CACHE / "sleeper_players.parquet",
    "Sleeper state": CACHE / "sleeper_state.parquet",
    "nflverse schedules": CACHE / "nflverse_schedules.parquet",
    "nflverse player_stats": CACHE / "nflverse_player_stats.parquet",
    "nflverse injuries": CACHE / "nflverse_injuries.parquet",
    "nflverse snap_counts": CACHE / "nflverse_snap_counts.parquet",
    "nflverse ff_playerids": CACHE / "nflverse_ff_playerids.parquet",
    "nflverse ff_opportunity": CACHE / "nflverse_ff_opportunity.parquet",
    "player_weeks": CACHE / "player_weeks.parquet",
}


def main():
    lines = ["# Data schema", "", "Columns were inspected from the cached real datasets before loader code was written.", ""]
    for name, path in DATASETS.items():
        frame = pl.read_parquet(path)
        lines.extend([
            f"## {name}",
            f"- Rows in inspected cache: {frame.height}",
            f"- Columns ({len(frame.columns)}): `" + "`, `".join(frame.columns) + "`",
            "",
        ])
    (ROOT / "docs/data_schema.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
