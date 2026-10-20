# Experiments

Adoption rule: at least 1% out-of-sample CRPS improvement in at least two of three test seasons.

## E1 slow consensus

Adopted: no

| Season | Baseline CRPS | Experiment CRPS | Improvement | Fitted coefficient(s) |
|---:|---:|---:|---:|---|
| 2023 | 2.945457 | 2.940554 | 0.166% | `0.20536294207872038` |
| 2024 | 2.921417 | 2.917729 | 0.126% | `0.17443985947929838` |
| 2025 | 2.896012 | 2.898583 | -0.089% | `0.17414706490196083` |

## E2 QB efficiency

Adopted: no

| Season | Baseline CRPS | Experiment CRPS | Improvement | Fitted coefficient(s) |
|---:|---:|---:|---:|---|
| 2023 | 2.945457 | 2.945199 | 0.009% | `{"TE": -0.09297128849041954, "WR": 0.07168574898768544}` |
| 2024 | 2.921417 | 2.921379 | 0.001% | `{"TE": -0.14138952151135495, "WR": 0.018302296528794688}` |
| 2025 | 2.896012 | 2.896147 | -0.005% | `{"TE": -0.13911286645274454, "WR": -0.022446042672932664}` |

## E3 Matchup

Skipped: Sleeper future-week projections were available for every remaining 2026 week through week 18.

## Overnight protocol

Adoption rule for E4-E10: improve the stated metric by at least 1% in at least 3 of 4 test periods (2023, 2024, 2025, 2026), with no period worsening by more than 1%. After six overnight experiments, the threshold becomes 2%.

## E4 Vegas totals — preregistered

- Hypothesis: pregame team implied points explain projection residuals and improve conditional score CRPS.
- Exact change: derive home/away implied points from `total_line` and `spread_line`; subtract the season-week league mean; fit one past-only least-squares coefficient per position. DEF uses the opponent implied points with the coefficient learned on that feature.
- Metric: sample-weighted CRPS across positions.
- Test periods: 2023, 2024, 2025, and completed 2026 weeks.
- Adoption threshold: >=1% CRPS improvement in at least 3 of 4 periods and no period worse by >1%.
- Result: rejected. CRPS improvements were 0.047% (2023), 0.157% (2024), 0.119% (2025), and 0.175% (2026); zero periods reached 1% and none worsened. Leakage check: maximum training season was S-1 for every test.
