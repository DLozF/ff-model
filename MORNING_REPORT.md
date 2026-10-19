# Morning report: 2026-10-19
## Status
| Phase | Status | Key result |
|---|---|---|
| P0 | done | Environment, config, git, and tests initialized |
| P1 | done | 35,741 training rows; scoring matched Sleeper on 96.93% |
| P2 | done | Greedy matched integer program on 1,000 rosters |
| P3 | blocked | Quantile model saved; strict all-season calibration gate failed |
| P4 | done | Availability sanity checks pass with documented defaults |
| P5 | done | Positive-definite copula; held-out stack ratio 1.1415 |
| P6 | done | 5,000-world synthetic season completed in 19.450s |
| P7 | done | Empty/clone/lopsided trade checks passed |
| P8 | done | 37,125 trades and 600 waivers screened in 845.893s |
| P9 | blocked | Copula Brier improved; stacked worst calibration decile was 6.51% |
| P10 | done | Yahoo and CSV loaders tested without logging in |
| P11 | done | E1/E2 rejected; E3 inapplicable |
## Key numbers
- 2026 distribution coverage 50/80/95 and CRPS vs Normal:
  - QB: 43.8% / 61.1% / 86.5%; 5.041 vs 5.164
  - RB: 39.6% / 76.3% / 90.1%; 3.229 vs 3.578
  - WR: 39.0% / 73.1% / 91.9%; 3.259 vs 3.626
  - TE: 31.5% / 78.2% / 93.1%; 2.568 vs 2.909
  - K: 43.4% / 67.6% / 84.1%; 2.997 vs 2.987
  - DEF: 54.4% / 77.8% / 95.6%; 2.785 vs 2.914
- Copula: QB1-WR1 correlation 0.313696; stack variance ratio 1.141456 vs independent 1.544908.
- Matchups overall: Brier 0.219201 copula vs 0.219208 independent; worst decile error 2.557%.
- Overall copula-minus-independent Brier: -0.00000784; paired week-bootstrap 95% interval [-0.00006456, +0.00004365].
- Stacked: Brier 0.217772 vs 0.217796; worst decile error 6.512% with 360 pairs.
- Stacked Brier difference: -0.00002415; 95% interval [-0.00019208, +0.00014881].
- n_final worlds + season runtime: 19.450 seconds; deterministic rerun passed.
## Synthetic league odds
| Team | P(playoffs) | P(bye) | P(champion) | Exp. wins |
|---|---:|---:|---:|---:|
| Team 1 | 0.6122 | 0.2476 | 0.1442 | 4.745 |
| Team 2 | 0.6158 | 0.2396 | 0.0872 | 4.864 |
| Team 3 | 0.6072 | 0.2346 | 0.0902 | 4.869 |
| Team 4 | 0.6908 | 0.2908 | 0.1302 | 5.172 |
| Team 5 | 0.4392 | 0.1266 | 0.0698 | 4.362 |
| Team 6 | 0.5404 | 0.1876 | 0.1028 | 4.545 |
| Team 7 | 0.3880 | 0.1024 | 0.0530 | 4.076 |
| Team 8 | 0.3852 | 0.1044 | 0.0592 | 4.104 |
| Team 9 | 0.3634 | 0.0872 | 0.0516 | 4.082 |
| Team 10 | 0.5050 | 0.1562 | 0.0984 | 4.530 |
| Team 11 | 0.3982 | 0.1012 | 0.0426 | 4.154 |
| Team 12 | 0.4546 | 0.1218 | 0.0708 | 4.497 |
## Sample trade report
- Team 1 gives AJ Barner and gets Christian McCaffrey from Team 5: **ACCEPT**; acceptance **UNLIKELY**.
- Team 1 delta: playoffs +0.2534 [0.2429, 0.2639]; champion +0.1900 [0.1790, 0.2010]; wins +1.0678 [1.0433, 1.0923].
- Team 5 playoff delta: -0.3008 [-0.3117, -0.2899].
## Assumptions I made
- Yahoo VERIFY settings remain the PLAN.md defaults until the real league is connected.
- P4 empirical injury estimates failed sanity checks; documented defaults were used, including r_IR=0.25 and kappa=0.75.
- P8 used raw post-trade WELP as a fast pre-screen, then exact roster balancing before confirmation.
- PuLP 4.1 had no solver binary; the reference lineup integer program used SciPy MILP.
## Blocked or failed
- P3: required K=500/smoothing=9 retry still missed strict coverage; 2026 TE 50% coverage was 31.5%, and K CRPS 2.997 did not beat Normal 2.987.
- P9: Brier passed overall and stacked, but the stacked worst decile error was 6.512%, above the 5% gate; the bin had 360 pairs, so it was not low sample.
## What Diego needs to do
1. Obtain Yahoo Fantasy API read approval, add credentials and league ID to `.env`, then follow `docs/YAHOO_SETUP.md` for the one-time login.
2. Run the documented `docker exec -it chronos ... scripts/load_yahoo.py` command; it will replace VERIFY settings and cache real rosters/standings.
3. Review the real scoring settings and team identity after import before trusting trade recommendations.
## Next phases to run
- Rebuild future worlds and league odds with Yahoo rosters, standings, scoring, schedule, and free agents.
- Rerun trade finder and waiver evaluator against the real league.
- Investigate P3's 2026 distribution shift and P9's stacked calibration miss before enabling automated recommendations.
