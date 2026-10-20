# Progress

## Status
| Phase | Status | Key result |
|---|---|---|
| P0 | done | 1 test passed; nflreadpy, pulp, polars import successfully |
| P1 | done | 35,741 training rows; score match 96.93%; 2026 projections through week 18 |
| P2 | done | Greedy matched integer program on 1,000 random rosters |
| P3 | blocked | Rolling b/s candidate improved CRPS in 3/4 seasons but failed strict coverage; not adopted |
| P4 | done | DEF exempt with h=0; corrected player h/r and injury-status estimates retained |
| P5 | done | QB1-WR1 r=0.3137; held-out stack variance ratio=1.1415 |
| P6 | done | FantasyCalc-V draft; week-7 start; 5,000 worlds + season in 18.526s |
| P7 | done | Market-ratio acceptance; Kyler Murray for Christian McCaffrey => ACCEPT/UNLIKELY |
| P8 | done | Market-first 37,125-trade finder completed in 473.502s |
| P9 | blocked | Copula Brier wins overall/stacked; stacked worst decile error 6.51% |
| P10 | done | Fake Yahoo JSON test passes; live and CSV loaders documented |
| P11 | done | E1/E2 below 1% adoption threshold; E3 skipped; all flags off |

## Assumptions
- Synthetic league uses the exact VERIFY defaults in PLAN.md until Yahoo is connected.
- Sleeper's Rotowire `pts_ppr` projection is the pregame projection source.
- `pulp_lineup` uses SciPy's MILP backend because installed PuLP 4.1 has no available solver binary.
- P4 corrected empirical h/r estimates are used for QB/RB/WR/TE/K. DEF is exempt because defenses only miss bye weeks: h_DEF=0 and r_DEF is unused.
- Historical IR transitions were unavailable; r_IR=0.25. QB replacement sample was 0, so kappa=0.75 and beta defaults WR/TE=0.6, RB=0.3.
- P8 applies FantasyCalc r >= 0.90 before raw post-trade roster WELP, then exact roster balancing and top-30 confirmation.
- FantasyCalc-unmatched players receive V=0 and are written to `logs/fantasycalc_unmatched.log`.
- Yahoo Fantasy API access currently requires manual approval before OAuth app use; setup documentation includes the approval step.

## Blocked
- P3 calibration gate: after rebuilding 2026 week 6 from nflverse actuals, the rolling eight-week b/s candidate improved sample-weighted CRPS in 2023, 2024, and 2026, but not 2025, and still failed the every-position coverage gate. It was not adopted. Full results: reports/calibration.md.
- P9 calibration gate: copula Brier beat independent overall (0.219201 vs 0.219208) and stacked (0.217772 vs 0.217796), but stacked worst equal-count bin error was 0.065119 (>0.05). Overall worst bin was 0.025570.

## Log
- P0: initialized project structure and git repository.
- P0 checks: `pytest -q` -> 1 passed; dependency import check exited 0.
- P1: cached Sleeper 2021-2025 weeks 1-18, 2026 completed weeks 1-5, and future projections weeks 6-18.
- P1: cached nflverse schedules, weekly stats, injuries, snap counts, ID map, and opportunity for 2021-2026.
- P1 checks: `player_weeks` 43,067 rows; 35,741 training rows; scoring match 25,377/26,180 (96.9328%).
- P1 checks: team-map test and full suite passed (9 tests).
- P2 checks: max greedy vs MILP difference < 1e-6 on 1,000 rosters; bye, injury, and FLEX cases passed.
- P2 full suite: 11 passed in 7.81s.
- P3: saved models/quantiles_2026.npz and reports/calibration.md; required K=500/smoothing=9 retry ran.
- P3 check: strict coverage/CRPS criterion false; continued with the saved retry model per three-strikes rule.
- P3 full suite: 16 passed in 7.99s.
- P4: saved availability.json and qb_effect.json with raw estimates, defaults, and sample sizes.
- P4 checks: all h/r and Out/Questionable sanity assertions passed after specified default replacement; 19 tests passed.
- P5: saved positive-definite 18D copula; minimum eigenvalue 0.403056 and QB1-WR1 correlation 0.313696.
- P5 checks: held-out 2025 stack variance ratio 1.141456 vs independent 1.544908; 21 tests passed.
- P6: generated 12 weeks x 5,000 worlds x 532 players under /tmp/ff-worlds/2026_w6.
- P6 checks: P(playoffs) sum=6.000000000000, P(champion) sum=1.000000000000, same-seed check passed, runtime 19.450s; 24 tests passed.
- P7: empty trade produced exact zero deltas; identical-world clone test produced NO CLEAR EFFECT.
- P7: lopsided Team 1 AJ Barner for Team 5 Christian McCaffrey produced ACCEPT; sample report saved; 27 tests passed.
- P8: screened all 37,125 requested trade shapes and 600 waiver pairs; 469 trades passed WELP and top 30 were confirmed.
- P8 checks: finder runtime 845.893s (<20 minutes); trade and waiver reports exist; 29 tests passed.
- P9: reran with antithetic draws and separate selection/simulation RNG streams; report saved from 14,400 matchup pairs.
- P9 check: Brier criteria passed; stacked calibration-bin gate failed; 30 tests passed.
- P9 follow-up: report now lists pair counts for both models in every calibration bin and paired week-bootstrap 95% intervals for copula-minus-independent Brier.
- P9 follow-up: stacked 6.51% error bin contains 360 pairs, so it is not marked low sample; full suite 33 passed.
- P10: implemented yfpy OAuth loader, Yahoo-to-Sleeper IDs, DEF mapping, Parquet tables, config update, CSV alternative, and real-league loading.
- P10 check: saved fake Yahoo JSON produced correct settings/rosters; full suite 32 passed. No Yahoo login attempted.
- P11: E1 improvements were 0.166%, 0.126%, -0.089%; E2 improvements were 0.009%, 0.001%, -0.005%.
- P11 checks: neither experiment met the 1% in 2-of-3 rule, E3 was inapplicable, all experiment flags remain off; 35 tests passed.
- P3 root cause: 2026 week 6 had projections and snap counts but no Sleeper actual-stat payload; snap-only rows were incorrectly marked played with zero points. Dataset logic now requires an actual-stat row before snap evidence can mark a player played.
- P3 rolling candidate: per-position b/s was fit by CRPS on only the prior eight completed weeks, including late prior seasons, then shrunk by n/(n+200). CRPS improved in 3/4 seasons, but strict coverage failed, so the base model remains active.
- P3 audit: all weekly b/s estimates, shrinkage weights, sample sizes, and exact prior-week keys are logged in logs/p3-rolling-parameters.json.
- P4 root causes: the injury join started from projection rows, excluding most Out players, and Markov estimation ignored absent middle weeks. Both were corrected before reevaluating defaults.
- P4 corrected estimates: Out P(play)=0.001757 (n=1,707), Questionable=0.653141 (n=2,292); both pass. QB/RB/WR/TE/K h and r pass. DEF is exempt, with h=0 and r unused. Full details: reports/availability.md.
- P3/P4 regression suite after fixes: 41 passed in 8.94s.
- Week-6 actual rebuild: nflverse scoring matched Sleeper within 0.5 on 1,510/1,568 rows (96.3010%) over 2026 weeks 1-5, exceeding the 95% requirement. Cached 338 scored nflverse week-6 rows and rebuilt player_weeks.
- Actual-source audit: found 22 completed team-week groups with projections and zero actual rows; all 22 were bye weeks and zero involved a scheduled game. Full list: reports/actuals_audit.md.
- P3 base-model week-6 comparison is recorded in reports/calibration.md. After rebuild, 2026 QB coverage changed from 0.438/0.611/0.865 to 0.529/0.719/0.933 and CRPS from 5.041 to 4.272; all positions are listed in the report.
- P4 follow-up: DEF is exempt from h/r sanity checks; h_DEF=0 and r_DEF is unused. This is recorded under Assumptions in models/availability.json and reports/availability.md.
- P6 base-model rerun starts at week 7 with 534 players and 5,000 worlds; runtime 18.695s, deterministic check passed, playoff probability sum=6 and champion probability sum=1.
- P7 base-model sample: Team 1 gives Rachaad White to Team 5 for Christian McCaffrey => ACCEPT / UNLIKELY. Team 1 playoff delta +0.2352 [0.2248, 0.2456], champion delta +0.1410 [0.1310, 0.1510].
- P8 base-model rerun: 37,125 candidates, 1,107 WELP passes, 30 confirmed trades, 10 confirmed waivers; solo runtime 1,189.548s (<20 minutes).
- P9 base-model rerun reproduced overall Brier 0.219201 copula vs 0.219208 independent and stacked 0.217772 vs 0.217796; stacked worst-bin error remains 0.065119.
- Final follow-up regression suite: 48 passed in 9.11s; rebuilt dataset verification returned 43,076 rows and 96.9689% scoring agreement.
- FantasyCalc: inspected 196 live redraft rows and cached them once for 2026-10-20 with a UTC fetch timestamp; schema recorded in docs/data_schema.md.
- Market join: 195 of 534 world players had positive V; 339 unmatched players were logged.
- Market acceptance tests: Henry for Coker + Monangai is UNLIKELY; an exact-value swap is LIKELY.
- Injury override test: a weeks=TBD override leaves availability unchanged.
- P6 market-draft rerun: 534 players, 5,000 worlds, 18.526s, deterministic; playoff sum=6 and champion sum=1.
- Jalen Hurts weeks=TBD override was not applied and is listed in generated reports as needing Diego's input.
- P7 market sample: Kyler Murray for Christian McCaffrey => ACCEPT/UNLIKELY, r=0.034, other receives V=275.0 and gives V=8016.0.
- P8 market-first rerun: 37,125 candidates, 19,648 market passes, 322 WELP passes, 30 confirmed trades, 10 waivers; runtime 473.502s.
- News check found 45 healthy players with trend30Day below -25% of V; list added to trade and waiver report tops.
- Model-vs-market report saved with the 15 largest within-position gaps each way among the top 150 by V.
- Final FantasyCalc regression suite: 53 passed in 9.19s; script compilation and `git diff --check` passed.
- Overnight 2026-10-20: instructions arrived at 07:23 Central, after the 07:00 experiment cutoff; queue was not started.
- Overnight safety: created tag `pre-overnight-2026-10-20` and branch `overnight-2026-10-20`; summary saved to reports/overnight_summary.md.
- Jalen Hurts override resolved to rest of season; P6 rebuilt in 19.513s and all 55,000 saved availability cells are false.
- Hurts-override P8 rerun: 37,125 candidates, 19,648 market passes, 323 WELP passes, 30 confirmed trades, 10 waivers; runtime 466.183s.
