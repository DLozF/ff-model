# Progress

## Status
| Phase | Status | Key result |
|---|---|---|
| P0 | done | 1 test passed; nflreadpy, pulp, polars import successfully |
| P1 | done | 35,741 training rows; score match 96.93%; 2026 projections through week 18 |
| P2 | done | Greedy matched integer program on 1,000 random rosters |
| P3 | blocked | Model/report saved; strict per-season coverage/CRPS gate failed after required retry |
| P4 | done | Availability sanity checks pass with declared defaults; QB effect defaults used |
| P5 | not started | |
| P6 | not started | |
| P7 | not started | |
| P8 | not started | |
| P9 | not started | |
| P10 | not started | |
| P11 | not started | |

## Assumptions
- Synthetic league uses the exact VERIFY defaults in PLAN.md until Yahoo is connected.
- Sleeper's Rotowire `pts_ppr` projection is the pregame projection source.
- `pulp_lineup` uses SciPy's MILP backend because installed PuLP 4.1 has no available solver binary.
- P4 empirical miss/recovery and injury-status estimates failed sanity checks, so the documented position/status defaults were used.
- Historical IR transitions were unavailable; r_IR=0.25. QB replacement sample was 0, so kappa=0.75 and beta defaults WR/TE=0.6, RB=0.3.

## Blocked
- P3 calibration gate: K=500/smoothing=9 retry still failed. Largest 2026 misses include TE 50% coverage=0.315, K 95%=0.841; DEF 2023 CRPS 3.216 vs Normal 3.150. Full results: reports/calibration.md.

## Log
- P0: initialized project structure and git repository.
- P0 checks: `pytest -q` -> 1 passed; dependency import check exited 0.
- P1: cached Sleeper 2021-2025 weeks 1-18, 2026 completed weeks 1-5, and future projections weeks 6-18.
- P1: cached nflverse schedules, weekly stats, injuries, snap counts, ID map, and opportunity for 2021-2026.
- P1 checks: `player_weeks` 43,067 rows; 35,741 training rows; scoring match 25,377/26,180 (96.9328%).
- P1 checks: team-map test and full suite passed (9 tests).
- P2 checks: max greedy vs MILP difference < 1e-6 on 1,000 rosters; bye, injury, and FLEX cases passed.
- P2 full suite: 11 passed in 7.81s.
- P3: saved models/quantiles_2026.npz and reports/calibration.md; required K=500/smoothing=9 retry ran.
- P3 check: strict coverage/CRPS criterion false; continued with the saved retry model per three-strikes rule.
- P3 full suite: 16 passed in 7.99s.
- P4: saved availability.json and qb_effect.json with raw estimates, defaults, and sample sizes.
- P4 checks: all h/r and Out/Questionable sanity assertions passed after specified default replacement; 19 tests passed.
