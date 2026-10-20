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

## E5 Rolling bias and spread — preregistered

- Hypothesis: an eight-week, per-position rolling CRPS calibration corrects recent bias and under/over-dispersion, especially QB 80% undercoverage.
- Exact change: for each test week, fit bias `b` and residual scale `s` using only the previous eight completed weeks, shrink toward identity with prior weight 200, and apply to that week's quantiles.
- Metric: sample-weighted CRPS across positions; QB 80% coverage is reported as a diagnostic.
- Test periods: 2023, 2024, 2025, and completed 2026 weeks.
- Adoption threshold: >=1% CRPS improvement in at least 3 of 4 periods and no period worse by >1%.
- Result: rejected. CRPS improvements were 0.719% (2023), 0.094% (2024), -0.009% (2025), and 0.036% (2026); no period reached 1%. QB 80% coverage moved 79.6%→79.6%, 79.9%→78.0%, 78.1%→78.0%, and 71.9%→72.4%.

## E6 Role change — preregistered

- Hypothesis: recent changes in offensive snap share improve RB/WR/TE projection accuracy.
- Exact change: for each player-week, compute mean offensive snap share over weeks t-2..t-1 minus weeks t-6..t-3; fit one past-only coefficient per RB/WR/TE and adjust projections.
- Metric: sample-weighted CRPS across RB, WR, and TE.
- Test periods: 2023, 2024, 2025, and completed 2026 weeks.
- Adoption threshold: >=1% CRPS improvement in at least 3 of 4 periods and no period worse by >1%.
- Result: rejected. RB/WR/TE CRPS improvements were 0.019% (2023), -0.003% (2024), -0.031% (2025), and -0.003% (2026). Feature coverage was 1,051/5,294, 1,161/5,340, 1,087/5,300, and 0/1,817 rows; no completed 2026 week yet has six prior 2026 weeks.

## E7 Heavier-tailed copula — preregistered

- Hypothesis: a t-copula better captures joint tail outcomes in stacked lineups than the Gaussian copula.
- Exact change: retain the fitted correlation matrix but sample multivariate t latent variables; compare 6 and 10 degrees of freedom. Choose on mean stacked Brier for 2023-2024, then evaluate the chosen df on 2025-2026.
- Metrics: stacked Brier (adoption metric) and stack variance ratio distance from 1 (diagnostic).
- Test periods: selection 2023-2024; held-out confirmation 2025 and completed 2026 weeks.
- Adoption threshold: >=1% stacked-Brier improvement in at least 3 of 4 periods and no period worse by >1%.
- Result: rejected. t10 was selected over t6 on 2023-2024, but versus Gaussian its stacked-Brier changes were -0.069% (2023), +0.081% (2024), -0.279% (2025), and -0.124% (2026 weeks 1-5; week 6 had no valid stacked lineup). Held-out 2025 stack variance ratio moved away from 1, 1.15008→1.15053.

## E8 Copula shrink — preregistered

- Hypothesis: changing correlation shrinkage improves stacked matchup calibration.
- Exact change: compare repaired-correlation/identity blends 1.0/0.0, 0.9/0.1 (current), and 0.8/0.2 using identical stacked lineups and random draws.
- Metrics: stacked Brier (adoption metric) and stack variance ratio distance from 1 (diagnostic).
- Test periods: 2023, 2024, 2025, and completed 2026 weeks.
- Adoption threshold: >=1% stacked-Brier improvement versus current 0.9/0.1 in at least 3 of 4 periods and no period worse by >1%.
- Result: rejected. Relative to current 0.9/0.1, no-shrink Brier changes were -0.009%, -0.004%, -0.012%, and +0.079%; 0.8/0.2 changes were +0.009%, +0.024%, -0.038%, and +0.020%. No period reached 1%. In the 2025 stack diagnostic, variance ratios were 1.109 (no shrink), 1.141 (current), and 1.176 (0.2 shrink); the variance gain alone does not satisfy the Brier adoption rule.

## E10 Risk-sensitive lineup tiebreak — preregistered

- Hypothesis: among players within 0.5 projected points, choosing higher variance for an underdog and lower variance for a favorite improves realized matchup win rate.
- Exact change: keep the higher projection when the gap exceeds 0.5; otherwise use model score variance as the tiebreak according to projected favorite status.
- Metrics: realized matchup win rate (adoption metric) and hindsight candidate points left on the bench.
- Test periods: 2023, 2024, 2025, and completed 2026 weeks.
- Adoption threshold: >=1% win-rate improvement in at least 3 of 4 periods and no period worse by >1%.
- Result: rejected. Relative win-rate changes were -0.319% (2023), -0.561% (2024), -0.745% (2025), and -2.372% (2026). Mean hindsight points left on the bench increased from 10.305→10.462, 10.369→10.388, 10.717→10.843, and 11.346→11.382.
