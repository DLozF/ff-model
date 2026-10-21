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
| T01 | done | Partial Yahoo import: league scoring refit, real roster in, P6/P8 rebuilt |
| T02 | done | Blend backtest rejected; explainers built; scorecard and misses written |
| T03 | done | FantasyCalc fallback fixed; daily and waiver jobs verified live |
| T04-1 | done | Market faller percentages use prior value; reports scoped and reordered |
| T04-2 | done | Distinct waiver adds, drop protection, priority gate, and tolerant Yahoo pool parser |
| T04-3 | done | Yahoo loader backs up, merges safely, reports conflicts, and preserves config on parse failure |
| T04-4 | done | Explainer snap and target shares use valid team-game denominators |

## Assumptions
- Synthetic league uses the exact VERIFY defaults in PLAN.md until Yahoo is connected.
- Sleeper's Rotowire `pts_ppr` projection is the pregame projection source.
- `pulp_lineup` uses SciPy's MILP backend because installed PuLP 4.1 has no available solver binary.
- P4 corrected empirical h/r estimates are used for QB/RB/WR/TE/K. DEF is exempt because defenses only miss bye weeks: h_DEF=0 and r_DEF is unused.
- Historical IR transitions were unavailable; r_IR=0.25. QB replacement sample was 0, so kappa=0.75 and beta defaults WR/TE=0.6, RB=0.3.
- P8 applies FantasyCalc r >= 0.90 before raw post-trade roster WELP, then exact roster balancing and top-30 confirmation.
- FantasyCalc-unmatched players receive V=0 and are written to `logs/fantasycalc_unmatched.log`.
- Yahoo Fantasy API access currently requires manual approval before OAuth app use; setup documentation includes the approval step.
- T04 Item 1 treats the top 15 waiver targets as the 15 free agents with the highest rest-of-season projection.
- T04 Item 2 treats an IR player's positive market value as evidence of an expected return; IR players at V=0 are droppable as out for the season.
- T04 Item 3 treats every pre-existing config value as the pasted-settings authority when Yahoo returns a conflicting value.

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
- Initial Jalen Hurts override had weeks unset and was not applied; it was later resolved to rest of season below.
- P7 market sample: Kyler Murray for Christian McCaffrey => ACCEPT/UNLIKELY, r=0.034, other receives V=275.0 and gives V=8016.0.
- P8 market-first rerun: 37,125 candidates, 19,648 market passes, 322 WELP passes, 30 confirmed trades, 10 waivers; runtime 473.502s.
- News check found 45 healthy players with trend30Day below -25% of V; list added to trade and waiver report tops.
- Model-vs-market report saved with the 15 largest within-position gaps each way among the top 150 by V.
- Final FantasyCalc regression suite: 53 passed in 9.19s; script compilation and `git diff --check` passed.
- Overnight 2026-10-20: instructions arrived at 07:23 Central, after the 07:00 experiment cutoff; queue was not started.
- Overnight safety: created tag `pre-overnight-2026-10-20` and branch `overnight-2026-10-20`; summary saved to reports/overnight_summary.md.
- Jalen Hurts override resolved to rest of season; P6 rebuilt in 19.513s and all 55,000 saved availability cells are false.
- Hurts-override P8 rerun: 37,125 candidates, 19,648 market passes, 323 WELP passes, 30 confirmed trades, 10 waivers; runtime 466.183s.
- Overnight Step 0: refreshed 2026 nflverse and Sleeper sources; completed weeks remain 1-6; rebuilt 43,076 player-weeks with 96.9689% scoring agreement.
- Overnight baseline frozen in reports/baseline_overnight.json: 24 position-period calibration rows, 14,400 matchup pairs, P6 19.513s, P8 466.183s, 54 tests.
- A1: all 196 FantasyCalc rows matched current Sleeper IDs; no unmatched top-100 player and no join fix required.
- A2: audited distribution, rolling, QB, copula, matchup, and availability fits; no leakage found. Added a shared pre-season split guard and regression test; 55 tests pass.
- A3: K beat Normal CRPS in all four periods. DEF lost only in 2023 (3.216 vs 3.150); a simpler empirical residual model still lost there and was rejected.
- A4: injury outcomes join on exact season/week/gsis_id. All sanity gates pass; Out n=1,707 at 0.001757 and Questionable n=2,292 at 0.653141.
- E4 rejected: Vegas implied-points CRPS gains were 0.047%/0.157%/0.119%/0.175% for 2023-2026, below the 1% adoption threshold in every period.
- E5 rejected: rolling bias/spread CRPS gains were 0.719%/0.094%/-0.009%/0.036%; QB 2026 80% coverage improved only 71.9% to 72.4%.
- E6 rejected: snap-share role adjustment changed RB/WR/TE CRPS by 0.019%/-0.003%/-0.031%/-0.003%; 2026 had no eligible six-week-history rows yet.
- E7 rejected: selected t10 stacked-Brier changes were -0.069%/+0.081%/-0.279%/-0.124%; 2025 stack variance ratio worsened 1.15008 to 1.15053.
- E8 rejected: no-shrink and 0.2-shrink stacked-Brier changes stayed within -0.038% to +0.079%, far below 1%; no-shrink improved the 2025 stack ratio to 1.109 but failed the adoption metric.
- E9 added: trade reports now include a score-spread/QB-availability stress verdict and label changed verdicts FRAGILE; the P7 sample remained ACCEPT/ROBUST.
- E10 rejected: variance tiebreak win-rate changes were -0.319%/-0.561%/-0.745%/-2.372%, and it left more hindsight points on the bench in every period.
- T01: parsed `data/yahoo_paste/` settings and roster into config; 17 of 17 model players matched (1 IDP excluded); free-agent pool estimated because `available.txt` was absent.
- T01: historical actuals rescored from nflverse stats plus new play-by-play bonus counts; projections rescored from Sleeper stat lines without unprojectable bonuses (mean residual QB 0.002, RB 0.026, WR 0.029, TE -0.017, K 0.104, DEF 0.060).
- T01: refit P3/P4/P5 and rebuilt P6 (18.271s, deterministic) and P8 (44,880 candidates, 24,184 market passes, 255 WELP passes, 30 trades, 10 waivers, 543.1s). Chalino Sánchez playoff probability 0.7444.
- T01: milestone tiers use highest-only; stacked mode is implemented and pending Diego confirmation. Trade deadline cutoff, playoff reseeding, and IDP-protection logic added with tests.
- T01: full suite 85 passed; same-seed reproducibility check passed. Assumption: IDP starter contributes his Yahoo projection weekly (0 on bye). Needs Diego: confirm stacked milestones, paste `available.txt`, approve Yahoo API.
- T02: walk-forward ridge-per-position and blend built (`src/ffm/backtest_projection.py`, `src/ffm/own_projection.py`); 23,520 predictions cached. Adoption rejected (0/4 periods >=1% MAE gain); `projection_source` stays `sleeper`.
- T02: `scripts/explain_week.py` produced six explainers (Nabers 2026 w4 + five random seeded picks); scorecard and bias-by-bucket saved to `reports/projection_scorecard.md`.
- T02: leakage, scoring, and determinism tests added; suite passed with `scripts/check.sh`. Assumption: `data/yahoo_paste/history/` absent, so Yahoo Fan-Pts cross-check was skipped.
- T03 A5 assumption: a `countered` offer counts as not accepted as proposed for the binary acceptance model. LIKELY uses fitted P(accepted)>=50% and POSSIBLE uses >=25% once 20 resolved offers exist; until then the original r=1.00/0.90 cutoffs remain active.
- T03 A5: `data/trade_log.csv` initialized locally and ignored by git; `scripts/log_trade.py` appends offers. Current status is 0/20 resolved, so reports retain the default acceptance thresholds.
- T03 A2: live world now has 535 players: 195 FantasyCalc, 272 model fallback, and 68 out. Full P8 comparison rerun produced 44,880 candidates, 24,184 market passes, 260 WELP passes, 30 trades, and 10 waivers in 551.802s.
- T03 A4: daily report shows latest weekly 80% coverage by position; QB was 82.8% on 29 played week-6 rows. QB E5 remains deferred until eight completed 2026 weeks.
- T03 automation: live daily completed in 124.493s; live waivers completed in 165.037s with 10 enriched moves. Both failure markers were cleared after success.
- T04 Item 1: prior-value percentage changes replace current-value division; V=37/trend=-181 is -83.03%. Current scoped news fell from 47 league-wide names to 3 roster/top-15 waiver names, capped at 10. Trade and waiver moves now precede injury/news sections, with news last.
- T04 Item 2: prior report had 10 rows but only 5 distinct adds. The rebuilt estimated pool gives all 11 synthetic opponents exactly one K and one DEF; the current protected run screened 680 pairs and found 0 qualifying distinct adds. Fresh `available.txt` pages are now the exclusive pool, with unparsed/unmatched lines logged. Rolling priority requires playoff gain >=0.03 plus a starting or bye-week role.
- T04 Item 3: Yahoo imports now validate all tables before writes, create `config.yaml.pre-yahoo-<timestamp>`, merge missing keys only, preserve milestones/40+ bonuses/IDP/waiver/trade/reseeding keys, and write conflicts to `reports/yahoo_load_diff.md`. A broken standings fixture left config byte-identical; a pass-TD conflict kept 6.0 over API 4.0. Partial import remains true unless all 12 rosters, standings, and a schedule are present.
- T04 Item 4: all six explainers reran. Snap/target old->new: Malik Nabers .0614/.0229 -> .6800/.2289; Emari Demercado .0078/.0000 -> .0900/.0000; Tanner Hudson .0095/.0029 -> .1600/.0291; Tyrod Taylor, Brian Thomas week 1, and Brandon Aubrey remained .0000/.0000 because no applicable prior role history.
