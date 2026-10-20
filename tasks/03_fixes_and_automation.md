# Task 03: Fix known issues and automate daily injuries and Tuesday waivers

You are Chronos. Project root: `/opt/data/ff-model` (host: `~/.hermes/ff-model`).

## Before you start
1. This prompt is `tasks/03_fixes_and_automation.md`. Commit it first if it is not committed.
2. Read `LESSONS.md`, `PROGRESS.md`, `README.md`, `reports/task02_summary.md` and `reports/league_import_summary.md` if they exist, and PLAN.md section A2. A2's rules apply.
3. Git: use branch `improve-2026-10` (create it from `overnight-2026-10-20` if missing). Never commit to `master`, never push.
4. Do not ask questions. Log assumptions in `PROGRESS.md`.
5. Same rules as before: no leakage; preregister every comparison in `reports/experiments.md`; adoption = at least 1% better in at least 3 of 4 periods with no period more than 1% worse; `scripts/check.sh` passes before every commit; one commit per item.

## Part A: Fixes, in this order

### A1. Container restarts
- `/tmp/ff-venv` and `/tmp/ff-worlds` disappear when the container restarts.
- Create `scripts/ensure_env.sh`. It rebuilds the venv if it is missing (uv path from `command -v uv`, falling back to `/usr/local/bin/uv`, with `/tmp` caches as in A2) and rebuilds worlds if the manifest says they are missing.
- Every script below calls it first.

### A2. FantasyCalc coverage bug
`logs/fantasycalc_unmatched.log` shows that players missing from FantasyCalc get V=0. That makes trades involving them look free. Example: the AJ Barner for Christian McCaffrey sample came out ACCEPT.

The unmatched players fall into 4 groups:
- (a) every K and DEF, because FantasyCalc does not value them
- (b) skill players outside FantasyCalc's ~196-player list (Tyrone Tracy, AJ Barner, Cade Otton, Chig Okonkwo, Greg Dulcich, Shedeur Sanders, Caleb Douglas)
- (c) players out for the season (Jalen Hurts)
- (d) any ID mismatch

Fixes:
- **Name match second pass:** when `sleeperId` is missing or differs, match on name plus position plus team.
- **Model fallback value:** per position, fit an isotonic (monotone) map from model rest-of-season points above replacement to FantasyCalc V on matched players. Apply it to unmatched players. K and DEF use their own small map, capped below the lowest matched FLEX-eligible V.
- **Out-for-season players** (`overrides.yaml` or Sleeper IR with no return) get V=0.
- **Source column:** add `value_source` with the values `fantasycalc`, `name_match`, `model_fallback`, or `out`, and show it in trade reports.
- **Tests:**
  - Unmatched healthy skill players get V > 0.
  - K and DEF V is below the lowest matched FLEX V.
  - The AJ Barner for McCaffrey trade is no longer ACCEPT/LIKELY.
- **Rerun** the P7 sample trades and P8, and report what changed.

### A3. P9 stacked calibration gate
- The fixed 5% worst-bin rule fails at 6.5% on a bin of 360 pairs. Random noise alone at that size is about 2.5% (1 SD), so the rule is too strict for the sample.
- Preregister a sample-size-aware test in `reports/experiments.md`: a per-bin binomial 95% interval for the actual win rate, plus a bootstrap expected calibration error (ECE) with a 95% interval. Explain why in writing and keep the old 5% result visible next to the new one.
- If stacked calibration still fails the new test, try walk-forward isotonic recalibration of win probabilities and judge it on Brier with the adoption rule.

### A4. QB 2026 undercoverage
- QB 80% coverage is 72% in 2026, on only about 5 weeks.
- Do not adjust anything yet. Add a weekly coverage line per position to the daily report.
- Preregister: once 2026 has 8 or more completed weeks, rerun E5 (rolling bias and spread) for QB only.

### A5. Trade acceptance thresholds
- The LIKELY/POSSIBLE/UNLIKELY cutoffs (r = 1.00 and 0.90) are guesses.
- Create `data/trade_log.csv` (add it to `.gitignore`) with columns: date, my_team_gives, my_team_gets, partner, r, model_verdict, outcome (accepted / rejected / countered / pending).
- Create `scripts/log_trade.py` to add a row from the command line.
- Once there are 20 or more resolved rows, fit a logistic regression of acceptance on r and update the cutoffs. Until then keep the current ones and say so in reports.

### A6. Lineup risk tiebreak (E10)
- Rejected. Leave it off. No work needed.

## Part B: Automation scripts (Chronos writes them, Diego installs the cron)

Create `scripts/run_job.sh <job>`:
- Calls `ensure_env.sh`.
- Uses `flock` on `/tmp/ff-job.lock` so two jobs never overlap.
- Runs under `nice -n 10` so Immich stays responsive.
- Logs to `logs/<job>_<YYYY-MM-DD>.log` and deletes logs older than 30 days.
- Exits non-zero on any failure, and writes `reports/JOB_FAILED_<job>.md` with the last 40 log lines. Delete that file on the next success.
- Jobs are pure Python: no LLM calls, so they work even when the GPT limit is hit.

### Job `daily` (runs every morning, plus Sunday before kickoff)
1. **Refresh data:** the Sleeper players table (`injury_status`, `status`), the nflverse injury report for the current week, Sleeper stats for any newly completed week, Sleeper projections for remaining weeks, and FantasyCalc.
2. **Injury diff:** compare to yesterday's saved snapshot (`data/injury_snapshots/YYYY-MM-DD.parquet`).
3. **Apply statuses automatically for the current week:**
   - Questionable, Doubtful, and Out use the P4 status play probabilities.
   - IR means out for at least 4 weeks, then the P4 return hazard applies.
   - `overrides.yaml` always wins over automatic status.
4. **Season-ending or long-term news** (IR, PUP, or a status change with no return timeline) for any rostered player: add a proposed `overrides.yaml` entry to `reports/injuries/needs_review.md`. Do not edit `overrides.yaml` yourself; Diego approves it.
5. **Forward-test snapshot:** run `scripts/daily_snapshot.py`. Once completed weeks exist, fill the forward-test table in `reports/model_vs_market.md`.
6. **Report:** write `reports/daily_latest.md` and a dated copy in `reports/daily/`:
   - Injury changes, Diego's roster first, then his opponent this week, then players on other rosters
   - Start/sit for this week: Diego's optimal lineup with each starter's 10/50/90 points and play probability
   - Healthy market fallers and risers (30-day FantasyCalc trend)
   - Weekly coverage line per position (from A4)
7. **Runtime budget:** under 10 minutes.

### Job `waivers` (Tuesday morning)
1. Run everything in `daily` first.
2. Rebuild P6 worlds from the upcoming week.
3. Add a `--waivers-only` flag to `scripts/find_moves.py` and run it.
4. Write `reports/waivers_latest.md` and a dated copy, with the top 10 add/drop moves:
   - Playoff and title probability gain with a 95% interval
   - Next-week projection and rest-of-season points
   - Bye-week coverage effect
   - FantasyCalc V and `value_source`
   - If `waiver_type` is FAAB, a suggested bid as % of remaining budget, scaled to the gain. If rolling, say whether the move is worth using priority.
   - Note which moves are only worth it for depth versus starting.
   - If the league is in partial import mode (Task 01), use `data/yahoo_paste/available.txt` when it was pasted in the last 7 days. Otherwise label every move "confirm the player is available on Yahoo before claiming".
5. **Runtime budget:** under 15 minutes.

### Install doc
- Write `docs/AUTOMATION.md` with the exact host crontab lines, and how to check the logs and the failure file.
- The cron runs on the OptiPlex host as `docker exec chronos bash -lc '/opt/data/ff-model/scripts/run_job.sh <job>'`. You cannot install the host crontab yourself.

**Tests:** a dry-run mode (`run_job.sh daily --dry-run`) that uses cached data with no network, and a test that the lock prevents overlap.

## Learning loop
- Append every failure, bug, or surprise to `LESSONS.md` (what happened, root cause, rule from now on).
- Save the rule in your own memory or skill feature too, if you have one.
- Read `LESSONS.md` before each part.

## Finish
- Run both jobs once by hand and confirm the reports exist.
- Update `PROGRESS.md`.
- Write `reports/task03_summary.md`: each fix with before/after numbers, the job runtimes, and a Needs Diego list.
- If the task passes 6 hours, stop at a clean commit and summarize what is left.
