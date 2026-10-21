"""Rebuild saved P6 worlds when the manifest points at a missing directory."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("/opt/data/ff-model")
MANIFEST = ROOT / "models/world_manifest.json"


def worlds_present() -> bool:
    """Return whether the manifest's world directory exists."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    world_dir = manifest.get("world_dir") or manifest.get("directory")
    return Path(world_dir).is_dir() if world_dir else False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    present = worlds_present()
    if args.check:
        return 0 if present else 1
    if present:
        print("worlds already present")
        return 0
    subprocess.run([sys.executable, str(ROOT / "scripts/run_synthetic.py")], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
