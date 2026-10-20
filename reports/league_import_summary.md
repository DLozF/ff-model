# League import summary (partial mode)

Date: 2026-10-20. Week 7. Opponents remain synthetic until full Yahoo import.

## Settings diff (old config.yaml -> parsed settings.txt)

- `my_team`: Team 1 -> Chalino Sánchez.
- `lineup`: QB/RB2/WR2/TE/FLEX/K/DEF -> adds `D: 1` (IDP slot).
- `pass_td`: 4 -> 6; `pass_int`: -1 -> -2.
- Added: yardage milestones (pass 2/3/4 at 300/350/400; rush 1/2/3 at 50/100/150; rec 1/2/3 at 100/150/200, mode `highest`), 40+ bonuses (completion 1, pass TD 2, run 1, rush TD 3, reception 1, rec TD 3), `off_fum_ret_td` 6, `def_fourth_down_stop` 2, `def_xp_return` 2, `def_kr_pr_td` 6.
- Added: `waiver_type: rolling`, `waiver_days: 2`, `weekly_waivers: Game Time - Tuesday`, `waiver_priority: 8`, `trade_deadline: November 28, 2026`, `playoff_reseeding: true`, `tiebreaker: higher_seed`, `ir_slots: 2`, `current_week: 7`, `partial_import: true`.
- `idp_scoring` stored (13 categories) but not modeled.

## Roster (18 rows; 17 matched to Sleeper IDs; 1 IDP excluded)

| Slot | Player | Pos | Sleeper ID | Match method |
|---|---|---|---|---|
| QB | Drake Maye | QB | 11564 | name+position+team |
| RB | Bucky Irving | RB | 11584 | name+position+team |
| RB | Jonathan Taylor | RB | 6813 | name+position+team |
| WR | Malik Nabers | WR | 11632 | name+position+team |
| WR | A.J. Brown | WR | 5859 | name+position+team (Q) |
| TE | Tyler Warren | TE | 12518 | name+position+team (Q) |
| W/R/T | Zay Flowers | WR | 9997 | name+position+team |
| K | Spencer Shrader | K | 12185 | name+position+team |
| DEF | Denver Broncos | DEF | DEN | defense-team |
| D | Kyle Hamilton | S | excluded | IDP fixed contribution |
| BN | Tyler Higbee | TE | 3271 | name+position+team |
| BN | Germie Bernard | WR | 13274 | name+position+team |
| BN | Xavier Worthy | WR | 11624 | name+position+team |
| BN | Malik Washington | WR | 11610 | name+position+team |
| BN | Tyler Shough | QB | 12545 | name+position+team |
| BN | KC Concepcion Jr. | WR | 13298 | name+position+team |
| IR | Jordyn Tyson | WR | 13281 | name+position+team (IR-R) |
| IR | Dylan Sampson | RB | 12469 | name+position+team (IR-R) |

Unmatched model players: none (`logs/yahoo_name_unmatched.log` is empty).

## Free agents

`available.txt` was absent, so the pool is every player not on Diego's roster or a synthetic roster (352 players). All waiver output is labeled: "Free agents are estimated; confirm on Yahoo before claiming."

## Rescoring

- Historical actuals rescored from raw nflverse stats plus play-by-play bonus counts (`nflverse_pbp_bonuses.parquet`, 2021-2026).
- Projections rescored from Sleeper projected stat lines with `include_bonuses=False` (milestone/40+ bonuses are not projectable); mean refit residual per position: QB 0.002, RB 0.026, WR 0.029, TE -0.017, K 0.104, DEF 0.060.
- Refit P3 quantiles, P4 availability/QB, P5 copula, and P6 worlds under league scoring. P8 rerun: 44,880 candidates, 24,184 market passes, 255 WELP passes, 30 confirmed trades, 10 waivers, 543.1s.
- Milestone tiers use highest-reached-only; stacked mode is also implemented (`milestone_mode: stacked`) for comparison.

## League odds (synthetic opponents)

- Chalino Sánchez: P(playoffs) 0.7444, P(bye) 0.3376, P(champion) 0.2132, expected wins 4.753, expected points 1015.47.

## Optimal lineup, Week 7 (Yahoo projections)

QB Drake Maye 23.61; RB Bucky Irving 17.02; RB Jonathan Taylor 17.29; WR Malik Nabers 15.50; WR A.J. Brown 14.71 (Q); WR Zay Flowers (flex) 18.60; TE Tyler Warren 10.73 (Q); K Spencer Shrader 8.05; DEF Denver Broncos 8.44; IDP Kyle Hamilton 7.95 (fixed). Starters total 141.90.

## Top 5 waiver moves (est. free agents)

1. Add Tyrone Tracy, drop Malik Washington: WELP +14.22, verdict metric +0.0364, ACCEPT.
2. Add Tyrone Tracy, drop Germie Bernard: WELP +13.98, +0.0372, ACCEPT.
3. Add Tyrone Tracy, drop Xavier Worthy: WELP +13.14, +0.0338, ACCEPT.
4. Add T.J. Hockenson, drop Malik Washington: WELP +13.11, +0.0264, ACCEPT.
5. Add Tyrone Tracy, drop KC Concepcion: WELP +13.07, +0.0350, ACCEPT.

Note: IR players Jordyn Tyson and Dylan Sampson are protected from waiver drops while they hold IR slots.

## Needs Diego

1. Confirm whether yardage milestone bonus tiers stack or only the highest tier counts. The model currently uses highest-only; stacked mode is implemented and can be switched in `config.yaml` (`scoring.milestone_mode`).
2. Paste `data/yahoo_paste/available.txt` (Players page filtered to Available) so the waiver pool is exact instead of estimated.
3. Yahoo API access is not approved yet; full import (other 11 teams, standings, schedule) will use `src/ffm/yahoo_loader.py` once approved.
4. IDP is excluded from trades and waivers by design; Kyle Hamilton contributes a fixed 7.95 points weekly (0 on his Week 13 bye).

## Limitations

- Other 11 teams are synthetic FantasyCalc-V drafts; league odds and trade ideas use synthetic opponents.
- Play-by-play bonus counting covers 2021-2026 source data cached 2026-10-20.
