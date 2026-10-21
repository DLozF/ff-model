# Expanded own-model features

- Baseline: Sleeper projection (`projection_source` remained `sleeper` after T04-5).
- Model: standardized per-position ridge, alpha 1.0, seed 2026, walk-forward.
- Features: Sleeper, last-3, season average, EWMA, snap/target/carry shares, implied points, spread, opponent points allowed, home, and QB change.
- All feature histories and training rows are strictly before each predicted week.
- Standard adoption rule: REJECTED.

## Period metrics

| Period | N | MAE base | MAE ridge | Improvement | Spearman base | Spearman ridge | RMSE base | RMSE ridge | Bias base | Bias ridge |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 7031 | 4.6533 | 4.7005 | -1.015% | 0.66514 | 0.67488 | 6.7203 | 6.6143 | +0.952 | +0.303 |
| 2024 | 7086 | 4.6339 | 4.6845 | -1.092% | 0.68842 | 0.69488 | 6.6979 | 6.5932 | +0.915 | +0.231 |
| 2025 | 7040 | 4.6671 | 4.7243 | -1.226% | 0.67102 | 0.67749 | 6.6005 | 6.5357 | +0.422 | -0.217 |
| 2026 | 2363 | 4.7202 | 4.8052 | -1.802% | 0.66248 | 0.66612 | 6.6157 | 6.5841 | +0.696 | +0.144 |

## Position metrics

| Pos | N | MAE base | MAE ridge | Spearman base | Spearman ridge |
|---|---:|---:|---:|---:|---:|
| DEF | 1790 | 5.8517 | 5.7203 | 0.30204 | 0.31237 |
| K | 1809 | 3.7130 | 3.6743 | 0.13466 | 0.13891 |
| QB | 2171 | 7.5242 | 7.8078 | 0.53479 | 0.53216 |
| RB | 5036 | 4.4459 | 4.5643 | 0.73696 | 0.74031 |
| TE | 4503 | 3.4549 | 3.4581 | 0.58072 | 0.59131 |
| WR | 8211 | 4.6389 | 4.6844 | 0.63586 | 0.63948 |

HistGradientBoostingRegressor was not run because ridge failed the standard adoption rule; the task directs stopping when the gate is not met.
