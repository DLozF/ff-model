import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.daily_job import run_daily
from scripts.daily_snapshot import run_daily_snapshot


def publish_waiver_report(root: Path, local_date: str) -> Path:
    """Copy the dated P8 waiver report to latest and the dated archive."""
    source = root / "reports" / f"waivers_{local_date}.md"
    if not source.exists():
        raise FileNotFoundError(f"waiver report was not produced: {source}")
    archive = root / "reports/waivers" / f"waivers_{local_date}.md"
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, archive)
    latest = root / "reports/waivers_latest.md"
    shutil.copyfile(source, latest)
    return latest


def run_waivers(root: Path, dry_run: bool = False, now: datetime | None = None) -> Path:
    started = time.perf_counter()
    now = now or datetime.now(timezone.utc)
    local_date = now.astimezone(ZoneInfo("America/Chicago")).date().isoformat()
    run_daily(root, dry_run=dry_run, now=now)
    env = {**os.environ, "PYTHONPATH": str(root / "src")}
    if not dry_run:
        subprocess.run(
            [sys.executable, str(root / "scripts/run_synthetic.py")],
            check=True, env=env,
        )
        run_daily_snapshot(root, now)
    subprocess.run(
        [sys.executable, str(root / "scripts/find_moves.py"), "--waivers-only"],
        check=True, env=env,
    )
    latest = publish_waiver_report(root, local_date)
    runtime = time.perf_counter() - started
    if runtime >= 900:
        raise RuntimeError(f"waivers job exceeded 15-minute budget: {runtime:.3f}s")
    print(f"waivers_runtime_seconds: {runtime:.3f}")
    return latest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(run_waivers(ROOT, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
