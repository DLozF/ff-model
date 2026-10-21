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

## T02-B Own projection blend — preregistered

- Hypothesis: a ridge regression per position on pregame features, blended walk-forward with the Sleeper projection, lowers MAE without hurting Spearman rank correlation.
- Exact change: per-position ridge on EWMA fantasy points (half-life fit on training data), snap/target/carry shares, red-zone opportunities, Vegas implied team points and spread, shrunk rolling opponent points allowed, home/away, QB-change flag, and Sleeper projection; blending weight fit walk-forward on past weeks only; trained only on weeks strictly before each test week (seasons from 2021).
- Metric: MAE across played player-weeks (adoption metric); within-week Spearman by period (must not be worse in any period); RMSE, bias, and CRPS reported.
- Test periods: 2023, 2024, 2025, and completed 2026 weeks.
- Adoption threshold: >=1% MAE improvement in at least 3 of 4 periods, no period worse by >1%, and Spearman not worse in any period.
- Config flag `projection_source: blend` only if adopted (default `sleeper`).
- Result: rejected. MAE improvements were 0.26% (2023), 0.19% (2024), 0.22% (2025), and 0.02% (2026); CRPS was slightly worse than Sleeper in every period (3.256 vs 3.252, 3.258 vs 3.251, 3.236 vs 3.233, 3.298 vs 3.293). Spearman improved in all four periods, but the MAE adoption rule failed in all four.

## T03-A3 Sample-size-aware stacked calibration — preregistered

- Hypothesis: the fixed 5% worst-bin error rule is too strict for bins near 360 pairs; a binomial 95% interval per bin plus a bootstrap ECE interval measures calibration without penalizing noise.
- Exact change: keep the current 5% rule visible alongside a new per-bin Wilson 95% interval for the actual win rate and a 1,000-replicate bootstrap of stacked ECE with a 95% interval; calibration fails only when a bin's nominal probability lies outside its Wilson interval or the ECE interval excludes zero in a conservative direction.
- Metric: stacked worst-bin Wilson exceedance and bootstrap ECE (adoption metric for any recalibration, if needed).
- Test periods: 2023, 2024, 2025, and completed 2026 weeks.
- Adoption threshold: recalibration is evaluated on stacked Brier with >=1% improvement in 3 of 4 periods and no period worse by >1%, if the new test still fails.
- Result: stacked calibration still fails. The fixed 5% worst-bin result is 6.512% (bin 1, n=360, predicted 0.343 vs actual 0.278). The Wilson 95% interval for that bin is [0.234, 0.326], which excludes the predicted 0.343, so the miscalibration is not explained by sample size. Stacked ECE is 0.0234 with a 95% interval [0.0003, 0.0234]. Overall has one smaller Wilson failure in bin 9 (predicted 0.796 vs actual 0.822, interval [0.801, 0.840]) and ECE 0.008. Bin table: `logs/task03-calibration-bins.csv`. Isotonic recalibration was not attempted because Brier improvement is judged under the standard adoption rule and the stacked gate's failure is real, not a noise artifact.

## T03-A4 QB 2026 undercoverage follow-up — preregistered

- Trigger: rerun E5 for QB only once the 2026 season has at least eight completed regular-season weeks; do not adjust the distribution before that trigger.
- Hypothesis: eight or more completed weeks provide enough recent data to judge whether rolling QB bias and spread correct the current 80% interval undercoverage.
- Exact change: fit the existing E5 eight-week rolling QB bias and residual scale using only weeks strictly before each tested week, with prior weight 200; compare against the unchanged base QB quantiles.
- Metric: QB CRPS is the adoption metric; 50%, 80%, and 95% coverage are diagnostics.
- Test periods and threshold: use the standard four periods (2023, 2024, 2025, completed 2026); adopt only with at least 1% CRPS improvement in at least 3 of 4 periods and no period worse by more than 1%.
- Current decision: deferred. The 2026 season has fewer than eight completed weeks, so no parameter change is allowed yet.

## T04-5 Expected league bonuses — preregistered

- Hypothesis: adding past-only expected milestone, 40+ yard play, long-TD, and defensive fourth-down-stop bonuses removes the known downward projection bias and improves accuracy.
- Exact change: for each test player-week, estimate yardage-threshold probabilities from nearest-projection empirical yardage residuals fit only on earlier weeks; compute both highest-tier and stacked milestone expectations and use `scoring.milestone_mode`. Estimate 40+ play rates per projected yard by position with shrinkage to the historical position mean, estimate long-TD shares from prior touchdowns, and estimate DEF fourth-down stops from the opponent's prior attempt rate times the defense's prior stop rate with league-mean shrinkage. Add the result to `rescored_proj` as `proj_pts_bonus`.
- Adoption metrics: MAE and within-week Spearman by period. Diagnostics: mean bias by position and projection bucket, and sample-weighted CRPS after refitting the quantile tables on the matching projection.
- Test periods: 2023, 2024, 2025, and completed 2026 weeks. Every week-W estimate uses rows and play-by-play strictly before week W.
- Task-specific adoption threshold: adopt if MAE is not worse than baseline by more than 0.5% in any period, mean bias moves closer to zero in at least 5 of 6 positions, and Spearman is not worse in any period.
- Standard-rule diagnostic: also report whether MAE improves by at least 1% in at least 3 of 4 periods with no period worse by more than 1%.
- Config change only if adopted: set `projection_source: sleeper_bonus`, refit quantiles, rerun calibration and P6 worlds, and report coverage, CRPS, and league odds before/after. Otherwise leave the model and config unchanged.
- Result: rejected. MAE changes were -0.036% (2023), +0.020% (2024), -0.792% (2025), and -0.838% (2026), so 2025 and 2026 exceeded the task-specific 0.5% worsening cap. Spearman improved in all four periods and mean bias moved closer to zero in 5/6 positions, but every adoption condition was required. The standard 1% rule also failed (0/4 periods improved by at least 1%). Sample-weighted CRPS changed 3.3049->3.3055, 3.2726->3.2699, 3.2420->3.2429, and 3.2993->3.3003. `projection_source` remains unchanged; calibration and P6 were not rerun. Full bias and coverage tables: `reports/expected_bonus.md`.

## T04-6 Expanded own-model features — preregistered

- Hypothesis: adding valid pregame opportunity, game-context, opponent, and quarterback-continuity features lets a per-position ridge model materially outperform the four-input Task 02 ridge.
- Exact change: retain Sleeper projection, last-3 average, season average, and EWMA; add prior-week snap share, target share, carry share, team implied points, team-perspective spread, home/away, rolling opponent points allowed to the position shrunk toward the league mean, and a flag for a projected starting-QB change from the prior game's primary passer. Every rolling value is computed from weeks strictly before the prediction week. Fixed ridge seed 2026.
- Baseline: Sleeper projection, because T04-5 was rejected and `projection_source` remains `sleeper`.
- Adoption metrics: played-player-week MAE and within-week Spearman by period. Diagnostics: RMSE and bias.
- Test periods: 2023, 2024, 2025, and completed 2026 weeks.
- Standard adoption threshold: at least 1% MAE improvement in at least 3 of 4 periods, no period worse by more than 1%, and Spearman not worse in any period.
- Model sequence: finish and test ridge first. Try HistGradientBoostingRegressor only if the ridge result leaves time and a justified next comparison; never tune after seeing test-period results. Stop after two hours if the standard gate is not met.
- Result: rejected. Expanded-ridge MAE changes versus Sleeper were -1.015% (2023), -1.092% (2024), -1.226% (2025), and -1.802% (2026), violating both the improvement requirement and the maximum-worsening guard in every period. Within-week Spearman improved in all four periods and RMSE declined, but the preregistered MAE gate controls adoption. HistGradientBoostingRegressor was not run because the task requires stopping when the standard gate is not met. `projection_source` remains `sleeper`. Full results: `reports/own_model_expanded.md`.

## Shadow test — 2026 weeks 7-12 — preregistered

- Frozen candidates: (a) current rescored Sleeper projection; (b) Sleeper plus only the past-only expected DEF fourth-down-stop bonus; (c) the fixed T04-6 standardized per-position ridge with its existing feature set, alpha 1.0, and seed 2026. No candidate changes the default projection during shadow testing.
- Pregame snapshots: save one immutable `data/shadow/2026_wNN.parquet` before that week's first kickoff. If a snapshot already exists, reuse it rather than recomputing with later information. Refuse a new snapshot at or after first kickoff.
- Quantiles: fit a separate quantile model for each candidate using only played rows with season-week keys strictly before the target week. Fit the candidate's residual distribution around that candidate's own walk-forward point projections; do not apply Sleeper bias corrections to another candidate. Store the pregame quantiles in the immutable snapshot.
- Test weeks: exactly 2026 weeks 7, 8, 9, 10, 11, and 12.
- Weekly metrics: within-week Spearman by position and sample-weighted CRPS. The weekly Spearman used for the adoption count is the sample-count-weighted mean of position Spearman coefficients with at least three scored players; all position values and sample sizes remain visible.
- Adoption rule, frozen now: a non-Sleeper candidate is eligible only if its weekly aggregate Spearman is strictly greater than Sleeper in at least 4 of the 6 test weeks **and** its sample-weighted CRPS over all scored rows from weeks 7-12 is no more than 0.5% worse than Sleeper. Never change this rule after seeing results.
- Decision timing: no adoption decision before week 12 is complete. Shadow reporting may identify an eligible candidate after all six weeks, but this task never changes `projection_source` automatically; the production default remains Sleeper unless a later explicit change is approved.
