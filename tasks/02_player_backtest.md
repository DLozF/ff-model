# Task 02: Player-week backtest and independent projection

You are Chronos. Project root: `/opt/data/ff-model` (host: `~/.hermes/ff-model`).

## Before you start
1. This prompt is `tasks/02_player_backtest.md`. Commit it first if it is not committed.
2. Read `LESSONS.md` (create it with a `# Lessons` header if missing), `PROGRESS.md`, `README.md`, and PLAN.md section A2 (environment). A2's rules still apply: absolute paths, uv with `/tmp` caches, venv at `/tmp/ff-venv` (rebuild if missing), 2 CPU cores and 7.5 GB RAM shared with Immich, run long jobs in the background with logs.
3. Git: if branch `improve-2026-10` exists, check it out. If not, create it from `overnight-2026-10-20`. Never commit to `master`. Never push; Diego pushes. Never commit `.env` or `data/cache/`.
4. Diego is not watching. Do not ask questions. Pick the simplest reasonable option and log it under Assumptions in `PROGRESS.md`.

## Hard rules
- **No leakage.** Every prediction for season S, week W uses only data that existed before that game's kickoff. No same-week stats, no later injury news, no end-of-season values.
- **Preregister.** Before running any comparison, write the hypothesis, exact change, metric, test periods, and adoption threshold in `reports/experiments.md`. Never change a threshold after seeing results. If you think a threshold was wrong, say why in writing and keep the original result visible.
- **Adoption rule:** improve the metric by at least 1% in at least 3 of 4 test periods (2023, 2024, 2025, completed 2026 weeks), with no period more than 1% worse.
- **Each item:** tests pass via `scripts/check.sh`, then one commit.
- **If you get switched to the fallback model mid-task,** finish the current item, run the checks, commit, and continue. Never skip checks.

## Goal
- Today the point projection is Sleeper's Rotowire projection, rescored to league scoring in Task 01. The model has never been tested on whether it can beat that, or simple baselines.
- Task 01 must be done first. Everything here uses league scoring from `config.yaml` (6-point pass TDs, yardage milestones, 40+ yard bonuses).
- Diego wants to pick any past player-week (example: Malik Nabers, 2026 week 4), have the model predict it using only pregame data, and compare the prediction to what actually happened.

## Part A: Single player-week explainer
Create `scripts/explain_week.py --player "Malik Nabers" --season 2026 --week 4`:
- **Inputs:** resolve the player by name, using Sleeper ID and nflverse gsis_id. If ambiguous, list the candidates and exit.
- **Pregame inputs:** show everything known before kickoff. Sleeper projection, last-3-game average, season-to-date average, snap share, target share, carries, team implied points from the Vegas lines, opponent, home/away, and injury status as of that week.
- **Prediction:** model median plus 10th/50th/90th percentiles from the quantile model, and the Part B projection once it exists.
- **Actual:** fantasy points recomputed from raw stats using `config.yaml` scoring, with a line-by-line breakdown (receptions, yards, TDs, fumbles, milestone and 40+ yard bonuses).
- **Result:** error (actual minus prediction), where the actual landed inside the predicted range as a percentile, and one line on the main cause of the miss (TD variance, in-game injury, role change, or stale projection).
- **Did not play:** if the player had a bye or didn't play, say so and show the availability probability the model gave.
- **Output:** save to `reports/explain/<player_slug>_<season>_w<week>.md`.
- Run it for Malik Nabers 2026 week 4, plus 4 more random 2026 player-weeks (seed 2026), one each for QB, RB, TE, and K.

## Part B: Independent projection, walk-forward
Create `src/ffm/own_projection.py`:
- **Features**, all computed only from games before the target week:
  - Exponentially weighted fantasy points (fit the half-life per position on training data)
  - Snap share, target share, carries share, red-zone opportunities if available
  - Team implied points and spread
  - Opponent points allowed to the position (rolling, shrunk toward the league mean)
  - Home/away, and a QB-change flag
  - Sleeper projection as one feature
- **Model:** start with ridge regression per position (scikit-learn is already in requirements). Try `HistGradientBoostingRegressor` only if ridge is finished and tested. Fixed seeds.
- **Walk-forward:** for each test week, train only on weeks before it. Training seasons start in 2021.
- **Blend:** `w * own + (1 - w) * sleeper`, with `w` fit walk-forward per position on past weeks only.

## Part C: Scorecard
Compare these predictors on every played player-week, by position and test period:
- B0 Sleeper projection (current)
- B1 last-3-game average
- B2 season-to-date average
- B3 own model
- B4 blend

Metrics:
- MAE, RMSE, and bias (mean of actual minus prediction)
- Within-week Spearman rank correlation, which matters most for start/sit
- CRPS after passing each through the quantile model

Write `reports/projection_scorecard.md`.

**Adoption:**
- If B3 or B4 meets the adoption rule on MAE, and Spearman is not worse in any period, make it the new `proj_pts` input behind a config flag `projection_source: blend` (default stays `sleeper` until adopted).
- If adopted, refit the P3 quantile tables on the new projection, because the old tables were fit on Sleeper residuals. Then rerun the calibration report and P6 worlds.

## Part D: Error analysis
- List the 50 largest 2026 misses, each tagged with a cause from Part A.
- Show bias per position, by projection bucket (low, mid, high).
- Write any repeated pattern (for example "TE projections above 12 run 1.5 points high") into `reports/projection_scorecard.md`.
- Also add each pattern to `LESSONS.md` if it should change future work.

## Tests to add
- **Leakage test:** shuffle or delete all rows at or after week W and assert that week-W features are unchanged.
- **Scoring test:** if `data/yahoo_paste/history/` has past-week team pages from Diego, recomputed points must match Yahoo's Fan Pts for those players. List any mismatch with the stat that causes it.
- **Determinism test:** same seed gives the same output.

## Learning loop
Whenever something fails, a bug turns up, or a result surprises you, append to `LESSONS.md`:
```
## YYYY-MM-DD: short title
- What happened:
- Root cause:
- Rule from now on:
```
If your agent framework has a memory or skill feature, save the rule there too. Read `LESSONS.md` again before each part.

## Finish
- Update `PROGRESS.md`.
- Write `reports/task02_summary.md`: the scorecard headline table, what was adopted or rejected with numbers, the Malik Nabers example result, and a "Needs Diego" list.
- If the whole task passes 6 hours, stop at a clean commit and write the summary with what is left.
