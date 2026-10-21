#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/data/ff-model"
PYTHON="/tmp/ff-venv/bin/python"
UV="$(command -v uv || true)"
if [[ -z "$UV" ]]; then
  for candidate in /usr/local/bin/uv "$HOME/.local/bin/uv" /tmp/uv-bin/uv; do
    if [[ -x "$candidate" ]]; then UV="$candidate"; break; fi
  done
fi
if [[ -z "$UV" || ! -x "$UV" ]]; then
  echo "uv not found" >&2
  exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "rebuilding /tmp/ff-venv"
  if [[ -d /tmp/ff-venv ]]; then
    rm -rf /tmp/ff-venv
  fi
  UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python \
    "$UV" venv /tmp/ff-venv --python 3.12
  UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python \
    "$UV" pip install --python /tmp/ff-venv/bin/python -r "$ROOT/requirements.txt"
fi

if ! /tmp/ff-venv/bin/python "$ROOT/scripts/rebuild_worlds.py" --check; then
  echo "rebuilding P6 worlds"
  PYTHONPATH="$ROOT/src" /tmp/ff-venv/bin/python "$ROOT/scripts/rebuild_worlds.py"
fi
