# Progress

## Status
| Phase | Status | Key result |
|---|---|---|
| P0 | done | 1 test passed; nflreadpy, pulp, polars import successfully |
| P1 | done | 35,741 training rows; score match 96.93%; 2026 projections through week 18 |
| P2 | done | Greedy matched integer program on 1,000 random rosters |
| P3 | not started | |
| P4 | not started | |
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

## Blocked
- None.

## Log
- P0: initialized project structure and git repository.
- P0 checks: `pytest -q` -> 1 passed; dependency import check exited 0.
- P1: cached Sleeper 2021-2025 weeks 1-18, 2026 completed weeks 1-5, and future projections weeks 6-18.
- P1: cached nflverse schedules, weekly stats, injuries, snap counts, ID map, and opportunity for 2021-2026.
- P1 checks: `player_weeks` 43,067 rows; 35,741 training rows; scoring match 25,377/26,180 (96.9328%).
- P1 checks: team-map test and full suite passed (9 tests).
- P2 checks: max greedy vs MILP difference < 1e-6 on 1,000 rosters; bye, injury, and FLEX cases passed.
- P2 full suite: 11 passed in 7.81s.
