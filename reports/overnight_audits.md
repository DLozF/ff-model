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
