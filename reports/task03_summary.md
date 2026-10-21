# Task 03 summary: fixes and automation

## A1 — container restart recovery

- Added `scripts/ensure_env.sh` and `scripts/rebuild_worlds.py`.
- Missing `/tmp/ff-venv` is rebuilt with `uv`; missing world directories are rebuilt from the manifest.
- Every automated job calls the environment check first.

## A2 — FantasyCalc coverage

Before:

- 195 of 534 modeled players had a positive FantasyCalc value.
- 339 players were unmatched and treated as V=0, including healthy skill players, all K/DEF, and unavailable players.
- Trade and waiver reports did not expose the source of a value.

After the live refresh:

- 535 modeled players: 195 `fantasycalc`, 272 `model_fallback`, 68 `out`.
- Second-pass matching uses normalized name + position + team.
- Healthy unmatched players receive a monotone model fallback; unavailable players receive V=0; reports show `value_source`.
- The A2 comparison run changed AJ Barner from V=0 to V=2 (`model_fallback`) against Christian McCaffrey V=8016 (`fantasycalc`), r=0.000249501 and UNLIKELY. The latest live market refresh is AJ V=1 and McCaffrey V=8256.
- A full current-roster AJ-for-McCaffrey P7 simulation was rejected because AJ is now a free agent, not on Diego's imported roster; no result was fabricated.
- Full P8 comparison rerun: 44,880 candidates, 24,184 market passes, 260 WELP passes, 30 trades, 10 waivers, 551.802 seconds.

## A3 — stacked calibration gate

- Kept the old fixed worst-bin result visible: 6.512% error on n=360.
- Added Wilson per-bin intervals and bootstrap ECE.
- The failure remains real: the predicted 0.343 is outside the bin's Wilson interval [0.234, 0.326]; stacked ECE 95% interval is [0.0003, 0.0234].
- No recalibration was adopted.

## A4 — QB coverage monitoring

- No distribution adjustment was made.
- Daily reports now show weekly 80% coverage for every position.
- Latest completed week: QB 82.8% (n=29), RB 81.7% (n=71), WR 82.0% (n=122), TE 75.8% (n=62), K 76.0% (n=25), DEF no played sample.
- QB-only E5 is preregistered to rerun after at least eight completed 2026 weeks.

## A5 — trade acceptance logging

- Created ignored local file `data/trade_log.csv` and `scripts/log_trade.py`.
- Current calibration sample: 0/20 resolved offers; default LIKELY/POSSIBLE cutoffs remain r=1.00/0.90.
- At 20 resolved offers, the code fits logistic acceptance on r. Countered offers count as not accepted as proposed; LIKELY is fitted P(accepted)>=50%, POSSIBLE is >=25%.

## Part B — automation

- `scripts/run_job.sh`: non-blocking `/tmp/ff-job.lock`, `nice -n 10`, dated logs, 30-day retention, non-zero failure propagation, and `JOB_FAILED_<job>.md` with the final 40 log lines.
- `daily`: refreshes current data, saves injury diffs, proposes long-term overrides without editing `overrides.yaml`, writes start/sit quantiles and play probabilities, market movers, coverage, and forward snapshots.
- `waivers`: runs daily, rebuilds worlds, runs `find_moves.py --waivers-only`, and writes top-10 moves with playoff/title 95% intervals, next-week/ROS values, bye coverage, value source, role, priority advice, and Yahoo availability warnings.
- Live daily runtime: 124.493 seconds; live waiver workflow runtime: 165.037 seconds. Both are within budget.
- Final verification: 121 tests passed and the reproducibility check passed.

## Adopted or rejected

Adopted:

- FantasyCalc second-pass matching and model fallback values.
- Sample-size-aware calibration diagnostics (the current stacked model still fails them).
- Weekly position coverage monitoring.
- Trade outcome logging and automatic future threshold fitting.
- Daily and Tuesday waiver automation.

Rejected/deferred:

- Stacked probability recalibration was not adopted.
- QB distribution changes are deferred until eight completed 2026 weeks.
- E10 lineup-risk tiebreak remains rejected/off.

## Needs Diego

1. Install the host crontab from `docs/AUTOMATION.md`.
2. Review `reports/injuries/needs_review.md`; current proposals are Jordyn Tyson and Dylan Sampson (IR). Copy approved entries into `overrides.yaml` manually.
3. Paste `data/yahoo_paste/available.txt`; until it is recent, every waiver is labeled for Yahoo availability confirmation.
4. Record trade outcomes with `scripts/log_trade.py`; 20 resolved offers are needed before thresholds can be calibrated.
5. Confirm highest-only versus stacked yardage milestone tiers.
6. Complete Yahoo API approval if live Yahoo import is still wanted.
