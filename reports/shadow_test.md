# Shadow projection test

- Default projection: unchanged (`sleeper`).
- Frozen test weeks: 2026 weeks 7-12.
- Rule: at least 4/6 weekly aggregate Spearman wins versus Sleeper and total sample-weighted CRPS no more than 0.5% worse.
- Quantiles are refit separately per candidate using only rows before each snapshot week.

## Snapshot status

| Week | Snapshot | Week complete |
|---:|---|---|
| 7 | saved | no |
| 8 | pending | no |
| 9 | pending | no |
| 10 | pending | no |
| 11 | pending | no |
| 12 | pending | no |

## Weekly aggregate

- No completed shadow weeks yet.

## Adoption status

- `def_stop`: pending; weeks scored 0/6; Spearman wins 0/6; total CRPS n/a; 0.5% guard not yet passed.
- `expanded_ridge`: pending; weeks scored 0/6; Spearman wins 0/6; total CRPS n/a; 0.5% guard not yet passed.
