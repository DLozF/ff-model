# Projection scorecard

Determinism seed: 2026. Predictions: `data/cache/projection_backtest.parquet`.

| Season | Predictor | MAE | RMSE | Bias | Spearman | CRPS |
|---:|---|---:|---:|---:|---:|---:|
| 2023 | B0 Sleeper projection | 4.653 | 6.720 | +0.952 | 0.6651 | 3.252 |
| 2023 | B1 last-3-game average | 5.292 | 7.500 | +0.102 | 0.5873 | 3.749 |
| 2023 | B2 season-to-date average | 5.204 | 7.146 | -0.251 | 0.5839 | 3.604 |
| 2023 | B3 own model | 4.708 | 6.622 | +0.335 | 0.6725 | 3.323 |
| 2023 | B4 blend | 4.641 | 6.672 | +0.820 | 0.6709 | 3.256 |
| 2024 | B0 Sleeper projection | 4.634 | 6.698 | +0.915 | 0.6884 | 3.251 |
| 2024 | B1 last-3-game average | 5.228 | 7.473 | +0.063 | 0.6126 | 3.728 |
| 2024 | B2 season-to-date average | 5.177 | 7.157 | -0.100 | 0.6012 | 3.644 |
| 2024 | B3 own model | 4.706 | 6.611 | +0.249 | 0.6917 | 3.333 |
| 2024 | B4 blend | 4.625 | 6.657 | +0.775 | 0.6926 | 3.258 |
| 2025 | B0 Sleeper projection | 4.667 | 6.600 | +0.422 | 0.6710 | 3.233 |
| 2025 | B1 last-3-game average | 5.361 | 7.617 | -0.077 | 0.5779 | 3.793 |
| 2025 | B2 season-to-date average | 5.237 | 7.186 | -0.253 | 0.5762 | 3.646 |
| 2025 | B3 own model | 4.729 | 6.540 | -0.175 | 0.6771 | 3.308 |
| 2025 | B4 blend | 4.657 | 6.563 | +0.299 | 0.6757 | 3.236 |
| 2026 | B0 Sleeper projection | 4.720 | 6.616 | +0.696 | 0.6625 | 3.293 |
| 2026 | B1 last-3-game average | 5.426 | 7.599 | +0.313 | 0.5714 | 3.843 |
| 2026 | B2 season-to-date average | 5.234 | 7.103 | +0.013 | 0.5813 | 3.659 |
| 2026 | B3 own model | 4.789 | 6.564 | +0.121 | 0.6683 | 3.361 |
| 2026 | B4 blend | 4.719 | 6.588 | +0.575 | 0.6656 | 3.298 |

## Decision

- Seasons meeting the 1% MAE improvement threshold: 0/4.
- No period worse by more than 1%: yes.
- Spearman not worse in any period: yes.
- Adopted: no.

## Error analysis patterns


| Position bucket | Sleeper bias (actual - projection) |
|---|---:|
| QB_low | +2.776 |
| QB_mid | +1.193 |
| QB_high | +1.311 |
| RB_low | +0.321 |
| RB_mid | +1.201 |
| RB_high | +1.195 |
| WR_low | +0.292 |
| WR_mid | +0.287 |
| WR_high | +1.149 |
| TE_low | +0.547 |
| TE_mid | +0.275 |
| TE_high | -1.466 |
| K_low | +0.819 |
| K_mid | +0.118 |
| DEF_low | +2.866 |
| DEF_mid | +4.414 |

## Largest 50 misses (2026, blend prediction)

See `logs/task02-largest-misses.csv` for the full list; causes come from Part A tagging.

| Name | Pos | Week | Projection | Blend | Actual | Abs error |
|---|---|---:|---:|---:|---:|---:|
| Tetairoa McMillan | WR | 4 | 15.87 | 15.70 | 47.20 | 31.50 |
| Tyquan Thornton | WR | 4 | 0.00 | 0.21 | 31.10 | 30.89 |
| Drake Maye | QB | 5 | 21.33 | 21.26 | 51.46 | 30.20 |
| Jaxon Smith-Njigba | WR | 2 | 19.51 | 19.51 | 48.50 | 28.99 |
| Davante Adams | WR | 2 | 13.66 | 13.63 | 42.50 | 28.87 |
| Kenneth Walker | RB | 1 | 13.63 | 13.73 | 41.10 | 27.37 |
| Jalen Coker | WR | 1 | 11.88 | 11.79 | 38.80 | 27.01 |
| Jaylen Warren | RB | 5 | 19.84 | 19.85 | 46.80 | 26.95 |
| Josh Allen | QB | 2 | 24.90 | 24.89 | 50.82 | 25.93 |
| CeeDee Lamb | WR | 4 | 17.42 | 17.40 | 43.30 | 25.90 |
| Bryce Young | QB | 1 | 18.61 | 18.62 | 44.44 | 25.82 |
| Christian Watson | WR | 5 | 15.57 | 15.52 | 41.30 | 25.78 |
| Christian Watson | WR | 1 | 12.55 | 12.52 | 37.70 | 25.18 |
| Carson Wentz | QB | 1 | 0.00 | 0.92 | 25.22 | 24.30 |
| Josh Allen | QB | 1 | 21.49 | 21.39 | 45.66 | 24.27 |
| Kyren Williams | RB | 4 | 13.75 | 13.87 | 37.70 | 23.83 |
| None | DEF | 5 | 5.83 | 6.60 | 30.00 | 23.40 |
| Caleb Williams | QB | 1 | 20.64 | 20.79 | 43.26 | 22.47 |
| Derrick Henry | RB | 1 | 15.27 | 15.45 | 37.30 | 21.85 |
| Brian Robinson | RB | 4 | 4.79 | 4.88 | 26.70 | 21.82 |
| None | DEF | 2 | 6.31 | 7.19 | 29.00 | 21.81 |
| Kyle Monangai | RB | 4 | 8.28 | 8.38 | 30.00 | 21.62 |
| Tre Tucker | WR | 6 | 9.07 | 9.09 | 30.70 | 21.61 |
| Omar Cooper | WR | 6 | 5.87 | 5.85 | 27.30 | 21.45 |
| Isaiah Likely | TE | 5 | 11.41 | 10.99 | 32.40 | 21.41 |
| Konata Mumpfield | WR | 3 | 2.01 | 2.07 | 23.30 | 21.23 |
| Parker Washington | WR | 5 | 14.31 | 14.23 | 35.40 | 21.17 |
| Jordan Love | QB | 5 | 19.08 | 19.18 | 40.28 | 21.10 |
| Kyler Murray | QB | 1 | 20.58 | 20.60 | -0.38 | 20.98 |
| Jared Goff | QB | 2 | 18.78 | 18.83 | 39.78 | 20.95 |
| D'Andre Swift | RB | 1 | 13.45 | 13.52 | 34.40 | 20.88 |
| None | DEF | 2 | 5.66 | 6.57 | 27.00 | 20.43 |
| Bucky Irving | RB | 5 | 15.24 | 15.27 | 35.50 | 20.23 |
| Tre Tucker | WR | 2 | 8.82 | 8.79 | 28.90 | 20.11 |
| Keon Coleman | WR | 4 | 4.82 | 4.91 | 24.60 | 19.69 |
| CeeDee Lamb | WR | 2 | 17.79 | 17.63 | 37.30 | 19.67 |
| Jaxson Dart | QB | 2 | 20.19 | 20.40 | 0.80 | 19.60 |
| Matthew Stafford | QB | 2 | 18.29 | 18.43 | 37.98 | 19.55 |
| Bijan Robinson | RB | 3 | 20.12 | 20.20 | 39.30 | 19.10 |
| Kyle Monangai | RB | 1 | 7.22 | 7.31 | 26.40 | 19.09 |
| Sam Darnold | QB | 3 | 19.82 | 19.60 | 38.66 | 19.06 |
| Sam Darnold | QB | 1 | 19.64 | 19.55 | 0.52 | 19.03 |
| Patrick Mahomes | QB | 2 | 19.98 | 20.05 | 38.98 | 18.93 |
| Drake London | WR | 3 | 13.47 | 13.48 | 32.40 | 18.92 |
| Case Keenum | QB | 3 | 12.71 | 12.67 | 31.48 | 18.81 |
| J.J. McCarthy | QB | 6 | 0.87 | 1.56 | 20.32 | 18.76 |
| Amon-Ra St. Brown | WR | 2 | 17.43 | 17.46 | 36.20 | 18.74 |
| Jahmyr Gibbs | RB | 3 | 23.56 | 23.67 | 42.40 | 18.73 |
| None | DEF | 1 | 2.89 | 3.33 | 22.00 | 18.67 |
| Ashton Jeanty | RB | 1 | 15.95 | 16.05 | 34.70 | 18.65 |
