# Expected-bonus projection

- Configured milestone mode: `highest`; both highest and stacked expectations were computed.
- Mean expected bonus on test rows: highest `0.420`, stacked `0.448` points.
- All estimates are walk-forward and use only earlier season-weeks.
- Task-specific adoption: REJECTED.
- Standard 1% rule: failed.

## Period metrics

| Period | N | MAE base | MAE bonus | Change | Spearman base | Spearman bonus | CRPS base | CRPS bonus |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 7031 | 4.6533 | 4.6550 | -0.036% | 0.66514 | 0.67091 | 3.3049 | 3.3055 |
| 2024 | 7086 | 4.6339 | 4.6330 | +0.020% | 0.68842 | 0.69096 | 3.2726 | 3.2699 |
| 2025 | 7040 | 4.6671 | 4.7041 | -0.792% | 0.67102 | 0.67644 | 3.2420 | 3.2429 |
| 2026 | 2363 | 4.7202 | 4.7597 | -0.838% | 0.66248 | 0.66401 | 3.2993 | 3.3003 |

Bias moved closer to zero in 5/6 positions.

## Position bias

| Pos | N | Base | Bonus |
|---|---:|---:|---:|
| QB | 2171 | +1.528 | +0.453 |
| RB | 5036 | +0.691 | +0.276 |
| WR | 8211 | +0.334 | +0.057 |
| TE | 4503 | +0.472 | +0.421 |
| K | 1809 | +0.450 | +0.450 |
| DEF | 1790 | +2.970 | +1.328 |

## Accuracy by position

| Pos | N | MAE base | MAE bonus | Spearman base | Spearman bonus |
|---|---:|---:|---:|---:|---:|
| QB | 2171 | 7.5242 | 7.5341 | 0.53980 | 0.53994 |
| RB | 5036 | 4.4459 | 4.4863 | 0.73703 | 0.73709 |
| WR | 8211 | 4.6389 | 4.6858 | 0.63796 | 0.63783 |
| TE | 4503 | 3.4549 | 3.4629 | 0.57592 | 0.57594 |
| K | 1809 | 3.7130 | 3.7130 | 0.12560 | 0.12560 |
| DEF | 1790 | 5.8517 | 5.6913 | 0.29331 | 0.29393 |

## Bias by projection bucket

| Pos | Bucket | N | Base | Bonus |
|---|---|---:|---:|---:|
| QB | low | 355 | +2.776 | +2.764 |
| QB | mid | 425 | +1.193 | +0.227 |
| QB | high | 1391 | +1.311 | -0.068 |
| RB | low | 2917 | +0.321 | +0.197 |
| RB | mid | 1668 | +1.201 | +0.502 |
| RB | high | 451 | +1.195 | -0.048 |
| WR | low | 4873 | +0.292 | +0.178 |
| WR | mid | 2914 | +0.287 | -0.170 |
| WR | high | 424 | +1.149 | +0.222 |
| TE | low | 3499 | +0.547 | +0.520 |
| TE | mid | 967 | +0.275 | +0.149 |
| TE | high | 37 | -1.466 | -1.791 |
| K | low | 859 | +0.819 | +0.819 |
| K | mid | 950 | +0.118 | +0.118 |
| DEF | low | 1669 | +2.866 | +1.230 |
| DEF | mid | 121 | +4.414 | +2.686 |

## Coverage diagnostics

| Period | Projection | Cov50 | Cov80 | Cov95 |
|---:|---|---:|---:|---:|
| 2023 | base | 0.510 | 0.832 | 0.956 |
| 2023 | bonus | 0.510 | 0.832 | 0.955 |
| 2024 | base | 0.515 | 0.829 | 0.955 |
| 2024 | bonus | 0.515 | 0.831 | 0.955 |
| 2025 | base | 0.484 | 0.823 | 0.958 |
| 2025 | bonus | 0.485 | 0.823 | 0.958 |
| 2026 | base | 0.445 | 0.799 | 0.955 |
| 2026 | bonus | 0.445 | 0.800 | 0.954 |
