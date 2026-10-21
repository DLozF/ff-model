import argparse
import sys
from pathlib import Path

import polars as pl

from ffm.yahoo_loader import (
    YahooTableError, fetch_yahoo_payload, load_csv_tables, load_yahoo_payload,
    load_yahoo_tables,
)

ROOT = Path("/opt/data/ff-model")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-dir", type=Path)
    args = parser.parse_args()
    ids = pl.read_parquet(ROOT / "data/cache/nflverse_ff_playerids.parquet")
    try:
        if args.csv_dir:
            tables = load_csv_tables(args.csv_dir)
            load_yahoo_tables(
                tables, ROOT / "config.yaml", ROOT / "data/cache",
                ROOT / "reports/yahoo_load_diff.md",
            )
        else:
            payload = fetch_yahoo_payload(ROOT / ".env")
            _, tables = load_yahoo_payload(
                payload, ids, ROOT / "config.yaml", ROOT / "data/cache",
                ROOT / "reports/yahoo_load_diff.md",
            )
    except YahooTableError as exc:
        print(f"Yahoo load failed in {exc.table} table: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"Loaded {tables['rosters'].height} roster rows across {tables['teams'].height} teams.")
    print("Updated config.yaml and cached normalized Yahoo tables.")


if __name__ == "__main__":
    main()
