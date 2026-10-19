import argparse
from pathlib import Path

import polars as pl

from ffm.yahoo_loader import (
    fetch_yahoo_payload, load_csv_tables, parse_yahoo_payload, save_tables, update_config,
)

ROOT = Path("/opt/data/ff-model")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-dir", type=Path)
    args = parser.parse_args()
    ids = pl.read_parquet(ROOT / "data/cache/nflverse_ff_playerids.parquet")
    if args.csv_dir:
        tables = load_csv_tables(args.csv_dir)
    else:
        payload = fetch_yahoo_payload(ROOT / ".env")
        tables = parse_yahoo_payload(payload, ids)
    save_tables(tables, ROOT / "data/cache")
    update_config(ROOT / "config.yaml", tables["settings"])
    print(f"Loaded {tables['rosters'].height} roster rows across {tables['teams'].height} teams.")
    print("Updated config.yaml and cached normalized Yahoo tables.")


if __name__ == "__main__":
    main()
