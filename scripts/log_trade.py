import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

COLUMNS = [
    "date", "my_team_gives", "my_team_gets", "partner", "r",
    "model_verdict", "outcome",
]
OUTCOMES = ("accepted", "rejected", "countered", "pending")


def append_trade(path: str | Path, row: dict) -> Path:
    """Append one trade offer, creating the CSV header when needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow({column: row[column] for column in COLUMNS})
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a trade offer to data/trade_log.csv")
    parser.add_argument("--give", required=True, help="Players my team gives")
    parser.add_argument("--get", required=True, help="Players my team gets")
    parser.add_argument("--partner", required=True)
    parser.add_argument("--r", required=True, type=float, dest="ratio")
    parser.add_argument("--model-verdict", required=True)
    parser.add_argument("--outcome", required=True, choices=OUTCOMES)
    parser.add_argument("--date", default=None)
    parser.add_argument("--path", default=str(ROOT / "data/trade_log.csv"))
    args = parser.parse_args()
    date = args.date or datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
    path = append_trade(args.path, {
        "date": date,
        "my_team_gives": args.give,
        "my_team_gets": args.get,
        "partner": args.partner,
        "r": f"{args.ratio:.6f}",
        "model_verdict": args.model_verdict,
        "outcome": args.outcome,
    })
    print(path)


if __name__ == "__main__":
    main()
