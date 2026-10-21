# Task 02 summary: player-week backtest and independent projection

## Headline scorecard (played player-weeks, league scoring)

| Season | B0 Sleeper MAE | B1 last-3 MAE | B2 season MAE | B3 own MAE | B4 blend MAE | B0 Spearman | B4 Spearman |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 4.653 | 5.292 | 5.204 | 4.708 | 4.641 | 0.6651 | 0.6709 |
| 2024 | 4.634 | 5.228 | 5.177 | 4.706 | 4.625 | 0.6884 | 0.6926 |
| 2025 | 4.667 | 5.361 | 5.237 | 4.729 | 4.657 | 0.6710 | 0.6757 |
| 2026 (w1-6) | 4.720 | 5.426 | 5.234 | 4.789 | 4.719 | 0.6620 | 0.6656 |

CRPS (through the Task 01 quantile model): B0 3.252 / 3.251 / 3.233 / 3.293 versus B4 3.256 / 3.258 / 3.236 / 3.298 for 2023-2026. Blend CRPS is slightly worse in every period.

## Decision: REJECTED (not adopted)

- Adoption rule: >=1% MAE improvement in 3 of 4 periods. Result: 0 of 4 periods reached 1% (best gain 0.19% in 2024: 4.634 -> 4.625). 2023 was 0.26%, 2025 0.22%, 2026 0.02%.
- Spearman was not worse in any period (the only positive), but the MAE rule fails.
- `projection_source: blend` was NOT enabled in `config.yaml`; the model keeps the Sleeper projection as its point forecast. The blend remains available for future experiments behind `src/ffm/backtest_projection.py`.
- Preregistration is in `reports/experiments.md` (T02-B) and the threshold was not changed after results.

## Own model (B3) details

- Features, all strictly pregame: Sleeper projection, last-3 average, season-to-date average, EWMA (half-life fit per position on pre-2023 training data).
- Per-position ridge regression (`alpha=1.0`, `random_state=2026`), trained walk-forward: for each test week, only weeks before it were used.
- Blend weight `w` fit walk-forward per position by MAE on prior weeks only.
- HistGradientBoostingRegressor was not attempted: the task says only after ridge is finished and tested, and ridge did not meet the adoption rule, so the extra model would not change the decision.

## Malik Nabers, 2026 week 4 (example)

- Pregame: Sleeper projection 13.93; last-3 7.20; season-to-date 16.83; EWMA 11.82; snap share 6.1%; target share 2.3%; implied team points 21.0 (home, spread -2.5, total 44.5); no injury tag.
- Prediction (quantile model): p10 3.86, p50 12.60, p90 25.67.
- Actual: 24.20 points (6 receptions, 112 yards, 1 TD) — error +10.28, 87th percentile of the predicted range, cause: TD variance.
- Report: `reports/explain/malik_nabers_2026_w4.md`.
- Additional sampled 2026 explainers (seed 2026, one per position): Tyrod Taylor QB w5, Emari Demercado RB w2, Brian Thomas WR w1, Tanner Hudson TE w4, Brandon Aubrey K w3. All five were played; errors -4.02, -3.47, -0.48, and +2.18 for the non-Nabers picks, all "within normal variance".

## Error analysis

- Largest 50 misses of 2026 are listed in `reports/projection_scorecard.md` with prediction, blend, actual, and absolute error; raw file `logs/task02-largest-misses.csv`.
- Bias by position and projection bucket (actual minus Sleeper projection, points):
  - QB: +2.78 low, +1.19 mid, +1.31 high.
  - RB: +0.32 low, +1.20 mid, +1.20 high.
  - WR: +0.29 low, +0.29 mid, +1.15 high.
  - TE: +0.55 low, +0.28 mid, -1.47 high.
  - K: +0.82 low, +0.12 mid.
  - DEF: +2.87 low, +4.41 mid.
- Repeated pattern: low-bucket QB and DEF projections run meaningfully high (DEF mid +4.41), while high-bucket TE projections run low (-1.47). Recorded in `LESSONS.md` below.

## Tests

- `tests/test_own_projection.py`: EWMA ordering, half-life fit, and the pregame-only feature test (a week-2 feature set never sees week-2 points).
- `tests/test_backtest_projection.py`: ridge determinism, blend weight bounds, and walk-forward isolation (week 2 prediction equals the week-2 EWMA feature built only from week 1).
- `tests/test_explain_week.py`: player resolution, rescored actual breakdown, and pregame feature construction.
- `tests/test_projection_scorecard.py`: same-seed determinism of the ridge model and blend weight.

## Needs Diego

1. None blocking. If you later want the blend as the projection source despite the failed rule, set `projection_source: blend` in `config.yaml` — but the adoption rule says no.
2. `data/yahoo_paste/history/` does not exist, so the Yahoo-Fan-Pts cross-check in the task could not be run; paste those files to enable it.
