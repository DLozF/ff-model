# Morning report: 2026-10-20

## Overnight run
- `OVERNIGHT.md` was received at 07:23 Central, after its 07:00 experiment cutoff.
- Safety tag and branch were created, but the experiment queue was not started to preserve the 07:30 reporting deadline.
- Details: `reports/overnight_summary.md`.

## Status
| Phase | Status | Latest result |
|---|---|---|
| P3 | blocked | Base model retained; strict per-position coverage gate still fails |
| P4 | done | Corrected availability model retained; DEF exempt with h=0 |
| P6 | done | Synthetic draft now uses FantasyCalc V; worlds rebuilt from week 7 |
| P7 | done | Acceptance now uses market package ratio; sample rerun completed |
| P8 | done | Market-first finder rerun in 466.183 seconds with Hurts out ROS |
| P9 | blocked | Stacked worst-bin calibration error remains 6.512% |

## FantasyCalc market integration
- Cached 196 redraft rows at `2026-10-20 06:24:48 UTC`; future runs reuse one Parquet cache per Central day.
- Joined by FantasyCalc `player.sleeperId`: 195 world players have positive V; 339 unmatched players are logged in `logs/fantasycalc_unmatched.log`.
- Package value = highest V + 0.5 x all other V; acceptance uses r = other-team received V / given V.
- Thresholds: LIKELY r >= 1.00; POSSIBLE 0.90-0.999; UNLIKELY below 0.90; OVERPAY above 1.25.
- Henry for Coker + Monangai test: UNLIKELY. Exact-value swap test: LIKELY.
- Healthy 30-day market fallers found: 45; the list is at the top of trade and waiver reports.
- `reports/model_vs_market.md` contains the 15 largest within-position rank gaps each way among the market top 150.

## Key numbers
- P3 2026 coverage 50/80/95 and CRPS: QB 0.529/0.719/0.933, 4.272; RB 0.459/0.843/0.961, 2.890.
- WR 0.446/0.782/0.954, 3.105; TE 0.374/0.809/0.953, 2.577.
- K 0.475/0.781/0.956, 2.630; DEF 0.544/0.778/0.956, 2.785.
- Copula: QB1-WR1 correlation 0.313696; held-out stack variance ratio 1.141456 vs 1.544908 independent.
- P9 Brier: overall 0.219201 copula vs 0.219208 independent; stacked 0.217772 vs 0.217796.
- P9 worst-bin error: overall 2.557%; stacked 6.512%.
- P6: 5,000 worlds, 534 players, 19.513 seconds; deterministic; playoff sum 6.000000000000; champion sum 1.000000000000.

## Synthetic league odds
| Team | P(playoffs) | P(champion) | Expected wins |
|---|---:|---:|---:|
| Team 1 | 0.6142 | 0.1220 | 4.219 |
| Team 2 | 0.8026 | 0.1780 | 5.006 |
| Team 3 | 0.6238 | 0.1094 | 4.477 |
| Team 4 | 0.4964 | 0.0926 | 3.901 |
| Team 5 | 0.5134 | 0.0800 | 4.165 |
| Team 6 | 0.3976 | 0.0492 | 3.771 |
| Team 7 | 0.2288 | 0.0254 | 3.100 |
| Team 8 | 0.3886 | 0.0484 | 3.612 |
| Team 9 | 0.6116 | 0.0950 | 4.285 |
| Team 10 | 0.5750 | 0.1010 | 4.144 |
| Team 11 | 0.4712 | 0.0658 | 4.110 |
| Team 12 | 0.2768 | 0.0332 | 3.210 |

## P7 sample trade
- Team 1 gives Kyler Murray to Team 8 for Christian McCaffrey.
- Verdict: ACCEPT; market acceptance: UNLIKELY; r=0.034; other team receives V=275.0 and gives V=8016.0.
- Team 1 playoff delta +0.2180 [0.2077, 0.2283]; other-team model playoff delta -0.2180 [−0.2284, −0.2076], info only.

## P8 finder
- 37,125 trades generated; 19,648 passed r >= 0.90; 323 passed WELP; top 30 confirmed; 30 ACCEPT trades reported.
- 600 waiver pairs screened; top 10 confirmed.
- Top trade: give Marvin Harrison + Jacoby Brissett for Brenton Strange; r=1.737 OVERPAY; playoff gain +0.1196; ACCEPT/LIKELY.
- Final suite: 54 passed in 9.06 seconds.

## Assumptions and blockers
- Yahoo remains disconnected; synthetic league settings remain active.
- Jalen Hurts is overridden out for the rest of the season; saved worlds contain 0 available cells out of 55,000.
- P3 remains blocked on strict coverage; P9 remains blocked on stacked calibration.
- `r_IR=0.25`, `kappa=0.75`, and WR/TE/RB beta defaults remain due insufficient samples.

## What Diego needs to do
1. Connect Yahoo using `docs/YAHOO_SETUP.md` when API approval is available.
