# Overnight audits

## A1 FantasyCalc join
- Daily API cache rows: 196.
- Rows matched to current Sleeper player IDs: 196.
- Unmatched API rows: 0.
- Unmatched players in the top 100 by redraft value: none.
- Conclusion: the `player.sleeperId` join does not drop FantasyCalc players; no fix required.

## A2 Leakage audit
- Distribution backtests fit on seasons strictly before each test season; the deployed model may use completed current-season weeks, which are prior information at forecast time.
- Rolling residual and QB-efficiency features use `shift(1)`; weekly bias/spread uses keys strictly before the target week.
- Copula and matchup fits use only pre-test-season rows. Availability and QB-effect models use 2021-2025 only.
- Added shared `rolling_origin_split` and a regression test proving fitting for season S excludes every S row.
- Result: no same-week or later feature leakage found; 55 tests pass.

## A3 K and DEF calibration
- K CRPS beats Normal in every test period: 2023 2.533 vs 2.566; 2024 2.672 vs 2.702; 2025 2.641 vs 2.677; 2026 2.630 vs 2.666.
- DEF CRPS is worse than Normal in 2023 only (3.216 vs 3.150), then better in 2024 (2.872 vs 2.956), 2025 (2.959 vs 3.040), and 2026 (2.785 vs 2.914).
- A simpler global empirical-residual distribution was tested. DEF CRPS was 3.212/2.879/2.969/2.782 for 2023-2026; it still lost to Normal in 2023 and was not consistently better than the current model.
- Conclusion: retain the current K/DEF quantile model; record the isolated 2023 DEF miss without adopting the simpler alternative.

## A4 Availability joins
- Final injury designations join to participation on exact `(season, week, gsis_id)` keys; the regression test retains Out players missing from projections.
- All gated sanity checks pass. Out P(play)=0.001757 (n=1,707); Questionable=0.653141 (n=2,292).
- Markov sample sizes (h/r): QB 2,399/553; RB 3,904/402; WR 6,215/632; TE 2,268/247; K 2,314/167; DEF h n=2,396 and r is exempt.
- No additional availability bug or sanity failure was found.
