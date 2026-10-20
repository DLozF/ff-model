# Morning report: 2026-10-20

## Status
| Phase | Status | Latest result |
|---|---|---|
| P3 | blocked | Week-6 actuals rebuilt; rolling b/s still fails strict coverage and remains off |
| P4 | done | DEF exempt with h=0; corrected player availability estimates retained |
| P6 | done | Base-model worlds rebuilt from week 7 |
| P7 | done | New lopsided sample trade returned ACCEPT |
| P8 | done | Trade and waiver finder rerun under the 20-minute gate |
| P9 | blocked | Rerun reproduced the stacked 6.51% calibration miss |

## Week-6 actual-stat rebuild
- nflverse scoring versus Sleeper, 2026 weeks 1-5: **1,510/1,568 = 96.3010%** within 0.5 points; required threshold was 95%.
- Accepted and cached **338** scored nflverse rows for 2026 week 6.
- Rebuilt dataset: **43,076 player-week rows**; historical 2021-2025 training rows remain **35,741**.
- Projection/actual scan found **22** completed team-week gaps. All 22 were bye weeks; **0** teams with scheduled games lacked actual rows.
- Full audit: `reports/actuals_audit.md`.

## P3 base-model impact of fixing week 6
| Pos | Coverage 50 before → after | Coverage 80 before → after | Coverage 95 before → after | CRPS before → after |
|---|---:|---:|---:|---:|
| QB | 0.438 → 0.529 | 0.611 → 0.719 | 0.865 → 0.933 | 5.041 → 4.272 |
| RB | 0.396 → 0.459 | 0.763 → 0.843 | 0.901 → 0.961 | 3.229 → 2.890 |
| WR | 0.390 → 0.446 | 0.731 → 0.782 | 0.919 → 0.954 | 3.259 → 3.105 |
| TE | 0.315 → 0.374 | 0.782 → 0.809 | 0.931 → 0.953 | 2.568 → 2.577 |
| K | 0.434 → 0.475 | 0.676 → 0.781 | 0.841 → 0.956 | 2.997 → 2.630 |
| DEF | 0.544 → 0.544 | 0.778 → 0.778 | 0.956 → 0.956 | 2.785 → 2.785 |

The rolling b/s candidate still improves sample-weighted CRPS in 3/4 seasons but fails strict per-position coverage, so the **base model remains active**. Full results: `reports/calibration.md`.

## P4 availability
- DEF only misses bye weeks: `h_DEF=0`.
- DEF is exempt from both h/r sanity gates; `r_DEF` is unused.
- `P(play | Out)=0.001757`, n=1,707.
- `P(play | Questionable)=0.653141`, n=2,292.
- Details: `reports/availability.md`.

## P6 base-model worlds
- First incomplete week: **7**.
- Players: **534**; worlds: **5,000**.
- Runtime: **18.695 seconds**.
- Same-seed reproducibility: passed.
- Sum P(playoffs): **6.000000000000**; sum P(champion): **1.000000000000**.

| Team | P(playoffs) | P(bye) | P(champion) | Expected wins |
|---|---:|---:|---:|---:|
| Team 1 | 0.5530 | 0.1890 | 0.1056 | 3.991 |
| Team 2 | 0.4640 | 0.1478 | 0.0718 | 3.872 |
| Team 3 | 0.5818 | 0.2170 | 0.1130 | 4.217 |
| Team 4 | 0.5540 | 0.2010 | 0.1112 | 4.174 |
| Team 5 | 0.5328 | 0.1832 | 0.1026 | 4.024 |
| Team 6 | 0.5872 | 0.2226 | 0.1038 | 4.371 |
| Team 7 | 0.4490 | 0.1368 | 0.0596 | 3.774 |
| Team 8 | 0.5066 | 0.1652 | 0.0530 | 4.045 |
| Team 9 | 0.4772 | 0.1412 | 0.0878 | 3.958 |
| Team 10 | 0.4612 | 0.1478 | 0.0878 | 3.864 |
| Team 11 | 0.5210 | 0.1778 | 0.0654 | 4.272 |
| Team 12 | 0.3122 | 0.0706 | 0.0384 | 3.437 |

## P7 sample trade
Team 1 gives **Rachaad White** to Team 5 for **Christian McCaffrey**:
- Verdict: **ACCEPT**; acceptance: **UNLIKELY**.
- Team 1 P(playoffs): **+0.2352** [0.2248, 0.2456].
- Team 1 P(champion): **+0.1410** [0.1310, 0.1510].
- Team 1 expected wins: **+0.8396** [0.8170, 0.8622].

## P8 finder
- Runtime: **1,189.548 seconds**; under the 1,200-second gate.
- Trades screened: **37,125**; WELP passes: **1,107**; confirmed: **30**.
- Waiver pairs screened: **600**; confirmed: **10**.
- Top trade: give Jalen Coker + Kyle Monangai for Derrick Henry; playoff gain **+0.1578**, ACCEPT/LIKELY.
- Top waiver: add Jalen Hurts, drop Denzel Boston; playoff gain **+0.0780**, ACCEPT.
- Final regression suite: **48 passed in 9.11s**.

## P9 matchup calibration
- Overall Brier: copula **0.219201**, independent **0.219208**; worst copula bin **2.557%**.
- Stacked Brier: copula **0.217772**, independent **0.217796**; worst copula bin **6.512%**.
- Stacked offending bin remains 360 pairs, not low sample.
- P9 remains blocked on the 5% stacked-bin gate.

## Remaining defaults/blockers
- `r_IR=0.25`, `kappa=0.75`, and WR/TE/RB beta defaults remain due insufficient samples.
- P3 remains blocked on strict coverage.
- P9 remains blocked on stacked calibration.
- Yahoo remains disconnected; synthetic league settings are still in use.
