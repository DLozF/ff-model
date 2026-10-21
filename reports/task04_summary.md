# Task 04 summary — reports, bonus model, Yahoo safety, full paste import

## Status

- Items 1-6: complete.
- Item 7 code: complete and tested; real-league activation is blocked on missing Yahoo paste files.
- Active projection source remains `sleeper`: both T04-5 and T04-6 were rejected by their preregistered accuracy gates.

## Item 1 — Healthy market fallers

- Before: `V=37`, `trend_30_day=-181` divided by current value and displayed about `-489%`.
- After: the prior value is `37 - (-181) = 218`; the report displays `-83.03%` and uses that same percentage for the `< -25%` filter.
- Players with a prior value at or below zero are skipped.
- Scope changed from 47 league-wide names to 3 names on Diego's roster or among the top 15 waiver targets; output is capped at 10.
- Trade and waiver moves now appear first; injury/news checks appear last.

## Item 2 — Waiver advice

- Before: 10 rows represented only 5 distinct adds because the same add was repeated with several drops.
- After: one best permissible drop per add, up to 10 distinct adds.
- Current protected-pool run: 680 add/drop pairs screened and 0 qualifying moves after WELP and drop protection. The report does not pad the list with duplicate or protected drops.
- High-value protection: market value `>=300` requires playoff gain `>=+0.05`.
- IR protection: an IR player with an expected return cannot be dropped; an out-for-season IR player at value 0 can be dropped.
- Rolling priority: “worth using priority” requires playoff gain `>=+0.03` and a starting or bye-week-starting role; otherwise “depth only, skip.”
- All 11 synthetic opponents now draft one K and one DEF, preventing elite kickers and defenses from remaining artificially free.
- A fresh `available.txt` is the exclusive pool. Concatenated Yahoo pages, attached injury tags, defenses, duplicates, and unparsed-line logging are supported.

## Item 3 — Yahoo loader safety

- Before: the fake-payload-tested loader could overwrite config directly and did not guarantee all-or-nothing parsing.
- After: every table is parsed and validated before writes; config is backed up as `config.yaml.pre-yahoo-<timestamp>`.
- Missing Yahoo keys preserve existing milestones, 40+ bonuses, IDP, waiver settings, trade deadline, and playoff reseeding.
- Conflict test: existing `pass_td=6.0` was retained over API `4.0` and reported in `reports/yahoo_load_diff.md`.
- Broken-standings test: `config.yaml` remained byte-identical.
- `partial_import` becomes false only when all expected teams have rosters and standings and a schedule exists.

## Item 4 — Explainer shares

All six explainers were regenerated. Values are snap share / target share:

- Malik Nabers, 2026 week 4: `6.14% / 2.29%` -> `68.00% / 22.89%`.
- Emari Demercado, 2026 week 2: `0.78% / 0.00%` -> `9.00% / 0.00%`.
- Tanner Hudson, 2026 week 4: `0.95% / 0.29%` -> `16.00% / 2.91%`.
- Tyrod Taylor, 2026 week 5: `0.00% / 0.00%` -> `0.00% / 0.00%`; no applicable prior role history.
- Brian Thomas, 2026 week 1: `0.00% / 0.00%` -> `0.00% / 0.00%`; no prior-week history.
- Brandon Aubrey, 2026 week 3: `0.00% / 0.00%` -> `0.00% / 0.00%`; target share is not applicable and no offensive role history exists.

Snap share now uses prior nflverse `offense_pct`; target share uses player targets divided by team pass attempts over the same prior weeks.

## Item 5 — Expected-bonus projection

**Decision: rejected.** Configured milestone mode is `highest`; both highest and stacked modes were computed. Mean expected bonus was `0.420` points in highest mode and `0.448` in stacked mode.

### Accuracy by period

| Period | MAE base | MAE bonus | MAE improvement | Spearman base | Spearman bonus | CRPS base | CRPS bonus |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 4.6533 | 4.6550 | -0.036% | 0.66514 | 0.67091 | 3.3049 | 3.3055 |
| 2024 | 4.6339 | 4.6330 | +0.020% | 0.68842 | 0.69096 | 3.2726 | 3.2699 |
| 2025 | 4.6671 | 4.7041 | -0.792% | 0.67102 | 0.67644 | 3.2420 | 3.2429 |
| 2026 completed | 4.7202 | 4.7597 | -0.838% | 0.66248 | 0.66401 | 3.2993 | 3.3003 |

The task-specific gate failed because 2025 and 2026 were more than 0.5% worse. The standard 1% rule also failed: no period improved by at least 1%. Spearman improved in all four periods.

### Mean bias: actual minus projection

| Position | Baseline | Expected bonus |
|---|---:|---:|
| QB | +1.528 | +0.453 |
| RB | +0.691 | +0.276 |
| WR | +0.334 | +0.057 |
| TE | +0.472 | +0.421 |
| K | +0.450 | +0.450 |
| DEF | +2.970 | +1.328 |

Bias moved closer to zero in 5 of 6 positions, but all adoption conditions were required. `projection_source` remains `sleeper`; calibration and P6 were not rerun because the model was rejected.

## Item 6 — Expanded own model

**Decision: rejected.** Added past-only snap, target, and carry shares; team implied points and spread; home/away; shrunk opponent points allowed by position; and QB-change status. The model was standardized per-position ridge with alpha 1.0 and seed 2026.

| Period | MAE base | MAE ridge | MAE improvement | Spearman base | Spearman ridge |
|---:|---:|---:|---:|---:|---:|
| 2023 | 4.6533 | 4.7005 | -1.015% | 0.66514 | 0.67488 |
| 2024 | 4.6339 | 4.6845 | -1.092% | 0.68842 | 0.69488 |
| 2025 | 4.6671 | 4.7243 | -1.226% | 0.67102 | 0.67749 |
| 2026 completed | 4.7202 | 4.8052 | -1.802% | 0.66248 | 0.66612 |

Spearman and RMSE improved, but MAE worsened beyond 1% in every period. The standard adoption rule failed. HistGradientBoostingRegressor was not run because the task directs stopping when the ridge gate is not met.

## Item 7 — Full-league paste import

- `.env` does not contain a configured `YAHOO_CLIENT_ID`, so the paste-import path was implemented.
- Added tolerant parsing for raw team roster pages, standings, and remaining-week schedules.
- Every unparsed or unmatched line is written to `logs/yahoo_paste_unparsed.log`.
- More than three unmatched players abort the import before config or cache writes and are printed under Needs Diego.
- A complete import sets `partial_import: false`, loads real rosters/standings/free agents, seeds simulations with current standings, uses the pasted remaining schedule, and labels P6/P8/waiver outputs `real league`.
- Full activation was not run because the required paste files are absent. The probe exited with code 2 before writes.

## Verification

- Final pre-summary suite: `142 passed`.
- `scripts/check.sh`: passed.
- Reproducibility hash check: passed (`306fc5b3ba98830b10366e5d3fbed05c51575651a10dcaa75b38318f288441c2`).
- Branch: `improve-2026-10`.
- No push was performed.

## Needs Diego

1. Paste the other league roster pages as `data/yahoo_paste/team_01.txt` through `team_12.txt` as applicable; `my_roster.txt` remains Diego's roster.
2. Paste current standings as `data/yahoo_paste/standings.txt`.
3. Paste each remaining regular-season matchup page as `data/yahoo_paste/schedule_wNN.txt`.
4. Then run: `cd ~/.hermes/ff-model && PYTHONPATH=src /tmp/ff-venv/bin/python scripts/parse_yahoo_paste.py --full`.
5. Push from the host after review: `cd ~/.hermes/ff-model && git push`.
