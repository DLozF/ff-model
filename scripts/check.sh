#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON=/tmp/ff-venv/bin/python

if [[ ! -x "$PYTHON" ]]; then
  echo "missing $PYTHON; create the virtual environment as documented in README.md" >&2
  exit 1
fi

cd "$ROOT"
"$PYTHON" -m pytest -q
PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}" \
  "$PYTHON" "$ROOT/scripts/reproducibility_check.py"
