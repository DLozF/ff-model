# Availability calibration

The original injury join used the projection-based player-week table as the left side, excluding most `Out` players. The corrected join starts from every final injury designation and determines participation from nflverse stats, snap counts, and observed player weeks.

## Markov sanity checks

| Pos | h estimate | h n | h check | h used | r estimate | r n | r check | r used |
|---|---:|---:|---|---:|---:|---:|---|---:|
| QB | 0.07901337792642141 | 2392 | pass | 0.079013 | 0.37735849056603776 | 530 | pass | 0.377358 |
| RB | 0.049259826442062275 | 3918 | pass | 0.049260 | 0.48258706467661694 | 402 | pass | 0.482587 |
| WR | 0.05164092664092664 | 6216 | pass | 0.051641 | 0.4849445324881141 | 631 | pass | 0.484945 |
| TE | 0.04717813051146384 | 2268 | pass | 0.047178 | 0.4251012145748988 | 247 | pass | 0.425101 |
| K | 0.02376836646499568 | 2314 | pass | 0.023768 | 0.3473053892215569 | 167 | pass | 0.347305 |
| DEF | 0.0 | 2276 | exempt | 0.000000 | NA | 0 | exempt | 0.800000 |

## Injury-status sanity checks

| Status | Estimate | N | Check | Value used |
|---|---:|---:|---|---:|
| Questionable | 0.6531413612565445 | 2292 | 0.5 < P(play) < 0.95: pass | 0.653141 |
| none | 0.9831520223152023 | 35850 | not gated: pass | 0.983152 |
| Out | 0.0017574692442882249 | 1707 | P(play) < 0.05: pass | 0.001757 |
| Doubtful | 0.0036363636363636364 | 275 | not gated: pass | 0.003636 |
| Note | 1.0 | 2 | not gated: pass | 1.000000 |

## Assumptions/defaults

- DEF is exempt from h/r sanity checks because defenses only miss bye weeks; h_DEF=0 and r_DEF is unused.
- Historical IR transitions unavailable; r_IR defaulted to 0.25.
