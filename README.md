# FF Model

## How to run everything

Run from the repository root. The cache commands use network access and may take time.

```bash
cd /opt/data/ff-model
UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python uv venv /tmp/ff-venv --python 3.12
UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python uv pip install --python /tmp/ff-venv/bin/python -r requirements.txt

# Cache source data (nflverse must run before Sleeper).
PYTHONPATH=/opt/data/ff-model/src /tmp/ff-venv/bin/python scripts/cache_nflverse.py
PYTHONPATH=/opt/data/ff-model/src /tmp/ff-venv/bin/python scripts/cache_sleeper.py

# Build the player-week dataset.
PYTHONPATH=/opt/data/ff-model/src /tmp/ff-venv/bin/python scripts/build_dataset.py

# Fit the distribution, availability/QB, and copula models in order.
PYTHONPATH=/opt/data/ff-model/src /tmp/ff-venv/bin/python scripts/fit_distributions.py
PYTHONPATH=/opt/data/ff-model/src /tmp/ff-venv/bin/python scripts/fit_availability_qb.py
PYTHONPATH=/opt/data/ff-model/src /tmp/ff-venv/bin/python scripts/fit_copula.py

# P6: generate saved worlds and synthetic-league season odds.
PYTHONPATH=/opt/data/ff-model/src /tmp/ff-venv/bin/python scripts/run_synthetic.py

# P7: run a deterministic empty-trade evaluation (replace arguments for a real trade).
PYTHONPATH=/opt/data/ff-model/src /tmp/ff-venv/bin/python scripts/evaluate_trade.py --team "Team 2" --give "" --get ""

# P8: find trade and waiver moves.
PYTHONPATH=/opt/data/ff-model/src /tmp/ff-venv/bin/python scripts/find_moves.py

# P9: run matchup calibration backtests.
PYTHONPATH=/opt/data/ff-model/src /tmp/ff-venv/bin/python scripts/matchup_backtest.py

# Run the full pytest suite and the same-seed reproducibility probe.
scripts/check.sh
```
