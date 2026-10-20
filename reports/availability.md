# Availability calibration

The original injury join used the projection-based player-week table as the left side, excluding most `Out` players. The corrected join starts from every final injury designation and determines participation from nflverse stats, snap counts, and observed player weeks.

## Markov sanity checks

| Pos | h estimate | h n | h check | h used | r estimate | r n | r check | r used |
|---|---:|---:|---|---:|---:|---:|---|---:|
| QB | 0.08086702792830346 | 2399 | pass | 0.080867 | 0.3688969258589512 | 553 | pass | 0.368897 |
| RB | 0.04943647540983607 | 3904 | pass | 0.049436 | 0.48258706467661694 | 402 | pass | 0.482587 |
| WR | 0.05181013676588898 | 6215 | pass | 0.051810 | 0.48575949367088606 | 632 | pass | 0.485759 |
| TE | 0.04717813051146384 | 2268 | pass | 0.047178 | 0.4251012145748988 | 247 | pass | 0.425101 |
| K | 0.02376836646499568 | 2314 | pass | 0.023768 | 0.3473053892215569 | 167 | pass | 0.347305 |
| DEF | 0.0 | 2396 | exempt | 0.000000 | NA | 0 | exempt | 0.800000 |

## Injury-status sanity checks

| Status | Estimate | N | Check | Value used |
|---|---:|---:|---|---:|
| none | 0.9831198906280517 | 35841 | not gated: pass | 0.983120 |
| Out | 0.0017574692442882249 | 1707 | P(play) < 0.05: pass | 0.001757 |
| Questionable | 0.6531413612565445 | 2292 | 0.5 < P(play) < 0.95: pass | 0.653141 |
| Doubtful | 0.0036363636363636364 | 275 | not gated: pass | 0.003636 |
| Note | 1.0 | 2 | not gated: pass | 1.000000 |

## Assumptions/defaults

- DEF is exempt from h/r sanity checks because defenses only miss bye weeks; h_DEF=0 and r_DEF is unused.
- Historical IR transitions unavailable; r_IR defaulted to 0.25.
