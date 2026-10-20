# FF-Model Overnight Improvement Run (instructions for Chronos)

Read this whole file once now. PLAN.md rules still apply (inspect before coding, cache, log, no invented numbers, no leakage, seeded randomness). If this file conflicts with PLAN.md, this file wins tonight.

Goal: make the model more accurate and its trade advice more trustworthy, without breaking anything. Diego is asleep. Never ask questions. Choose the simplest reasonable option and log it.

---

## 1. Safety rules (follow before anything else)
1. Rollback point: `git tag pre-overnight-2026-10-20`, then `git checkout -b overnight-2026-10-20`. All work stays on this branch. Never touch main, never push anywhere.
2. Only create or change files inside `/opt/data/ff-model` and your `/tmp` folders. Never change your own config, your model settings, your scheduled jobs, or Diego's other jobs.
3. Do not log in to Yahoo. Do not call any paid API. Use only your current model and the free data sources already in PLAN.md and FantasyCalc.
4. Machine limits: 2 CPU cores, 7.5 GB RAM, shared with Immich. One heavy job at a time. Use n_dev worlds for experiments; use n_final only for the final confirmation run.
5. Keep tool output short: `pytest -q`, `tail -n 30` on logs, never print whole tables.
6. Clock: check `TZ=America/Chicago date`. Do not start a new experiment after 17:00 Central. Final summary written by 18:00 Central.
7. Stop conditions (write the summary, then end, do not retry in a loop):
   - 3 rate-limit, quota, or auth errors in a row from your model
   - Tests failing that you cannot fix in 3 attempts (revert to the last passing commit first)
   - Disk above 90% or repeated out-of-memory kills
   - The queue in section 4 is finished. Do not invent busywork.
8. Commit after every adopted change or bug fix, with a one-line message.

## 2. Step 0: Baseline (15 minutes max)
1. Refresh nflverse and Sleeper data for any newly completed 2026 weeks. Rebuild `player_weeks`.
2. Run the full test suite. Write `reports/baseline_overnight.json` with: per-position 50/80/95 coverage and CRPS for each test period, copula stack variance ratio, matchup Brier (overall and stacked) with worst calibration bin, P6 runtime, P8 runtime, test count.
3. These numbers are the "before" for everything tonight. Never overwrite them.

## 3. Experiment protocol (applies to every experiment in section 4)
1. Pre-register first. Before running, append to `reports/experiments.md`: id, hypothesis, exact change, metric, test periods, adoption threshold. Never edit a pre-registered row afterward except to add the result.
2. No leakage. Any new parameter is fit only on data before the test period (rolling origin, same as P3). Test periods: 2023, 2024, 2025, and 2026 completed weeks.
3. Adopt only if the metric improves by at least 1% in at least 3 of the 4 test periods and worsens by more than 1% in none. After 6 experiments have been run, raise the bar to 2%. Reason: many tries against the same test data produce false wins.
4. Limits: at most 12 experiments tonight, at most 45 minutes each. If one runs over, abandon it and log "timeout".
5. Adopted changes go behind a config flag, switched on. Rejected changes stay in the code but switched off, with the result logged.
6. After an adoption, run the full tests and a same-seed reproducibility check. If either fails, revert.
7. Rerun P6 to P9 once at the end (not after each experiment), only if an adopted change affects them.

## 4. Work queue (in this order)

### A. Audits and bug fixes (no threshold; fix anything wrong and add a test for it)
- A1 FantasyCalc join: report rows returned by the API, rows matched to Sleeper IDs, and any unmatched player in the top 100 by value. Fix the join if it drops players.
- A2 Leakage audit: read every feature and fitting function. Confirm none uses same-week or later information. Add a test that fitting for season S never reads S rows.
- A3 K and DEF: report coverage and CRPS vs the Normal baseline for the rebuilt data. If either is worse than Normal, say so and test a simpler distribution for them.
- A4 Availability: confirm injury-status rows are joined to the right week. Report any other sanity-check failure and its sample size.

### B. Accuracy experiments
- E4 Vegas totals: if `load_schedules` has `spread_line` and `total_line`, compute each team's implied points. Adjust projections by `b_pos x (implied points minus league average)`, one b per position, fit on prior seasons. For DEF use the opponent's implied points. Metric: CRPS.
- E5 Rolling bias and spread: redo the earlier rolling per-position b and s calibration on the bug-fixed data, this time judged by the section 3 CRPS rule. Pay special attention to QB (80% coverage was only 72%).
- E6 Role change: for RB, WR, TE, adjust by the change in snap share (last 2 weeks vs the prior 4 weeks) using `load_snap_counts`. Metric: CRPS.
- E7 Heavier-tailed copula: replace the Gaussian copula with a t-copula (try 6 and 10 degrees of freedom, choose on 2023 and 2024, test on 2025 and 2026). Metrics: stack variance ratio closer to 1 and lower stacked Brier. Adopt under the same rule using stacked Brier.
- E8 Copula shrink: compare 1.0/0.0, 0.9/0.1, 0.8/0.2 blends with the identity matrix. Same selection rule as E7.

### C. Decision-layer improvements (judge by tests, not thresholds)
- E9 Fragile-verdict check: add to every trade report a stress run with score spread multiplied by 1.25 and QB availability set to the pessimistic case. If the verdict changes, label it FRAGILE and say why. Add tests.
- E10 Risk-sensitive lineup tiebreak (low priority): when two candidates are within 0.5 projected points, test choosing the higher-variance one for an underdog and the lower-variance one for a favorite. Report hindsight points left on the bench and simulated win rate. Adopt only under the section 3 rule using win rate.

### D. Engineering
- D1 Forward test: write `scripts/daily_snapshot.py`. It saves, with a timestamp, the FantasyCalc values and the model's rest-of-season projections, and after each week finishes it adds actual points and reports which ranking (model or market) was closer, by position, into `reports/model_vs_market.md`. Do not install a scheduled job. Put the exact cron line in the summary for Diego.
- D2 Speed: profile the P8 trade finder. Target under 5 minutes with the same results (verify identical top 10).
- D3 Add `scripts/check.sh` that runs the tests and a reproducibility check. Update README with a short "how to run everything" section.

### E. Self-generated experiments (only if A to D are done and time remains)
Group out-of-sample residuals by position, home or away, week of season, and team. Find the largest systematic bias. Pre-register up to 4 more experiments (within the 12-experiment limit) and run them under the same protocol.

## 5. Reporting
- After each experiment, add the result row to `reports/experiments.md` and at most 5 lines to PROGRESS.md.
- At the end write `reports/overnight_summary.md` (under 70 lines) and update MORNING_REPORT.md. Required sections:
  1. Before vs after table using the baseline file (coverage, CRPS, Brier, stack ratio, runtimes, test count)
  2. Adopted changes (one line each, with the numbers that justified them)
  3. Rejected or timed-out experiments (one line each)
  4. Bugs found and fixed
  5. Anything that needs Diego (open questions, the Jalen Hurts override is still pending a number of weeks, do not apply it)
  6. Morning commands for Diego: how to review the branch diff, how to merge `overnight-2026-10-20` into main, how to roll back to the tag, and the cron line from D1
- Your last message should be 10 lines or fewer: what improved, what did not, what Diego must do.
