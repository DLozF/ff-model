# Task 04: Report fixes, bonus model, Yahoo loader safety, full-league paste import

## Before you start
1. This prompt is `tasks/04_reports_bonus_and_loader.md`. Commit it first if it is not committed.
2. Read `LESSONS.md`, `PROGRESS.md`, `README.md`, `reports/task02_summary.md`, `reports/task03_summary.md`, and `PLAN.md` section A2. A2's rules apply.
3. Git: use branch `improve-2026-10`. Never commit to master. Never push; Diego pushes from the host.
4. Do not ask questions. Log assumptions in `PROGRESS.md`.

## Hard rules
- No leakage. Every prediction for season S, week W uses only data that existed before kickoff.
- Preregister every comparison in `reports/experiments.md` BEFORE running it. Never change a threshold after seeing results.
- Standard adoption rule: at least 1% improvement in at least 3 of 4 periods (2023, 2024, 2025, completed 2026 weeks), with no period more than 1% worse.
- One item, one commit. `scripts/check.sh` must pass before each commit.
- Iteration discipline (a lesson from the last run):
  - When a test fails, read the failure and fix the test data or the code. Never add debug prints or rerun pytest in a loop.
  - Make at most 2 attempts at the same failure. After that, mark that single test xfail with the reason, log it in `LESSONS.md`, and move on.
  - If you are close to your iteration limit, stop at a clean commit and write the summary.
- Telegram: send Diego a 5-line update after each item (what changed, key numbers, anything blocked).
- Fallback model: if you are switched to the fallback model, keep going and never skip checks.

## Item 1: "Healthy market fallers" bug (trade and waiver reports)
- Bug: `trend_pct = 100 * trend_30_day / market_value` divides by the CURRENT value. For V=37, trend=-181 it prints -489%.
- Fix: the base is the value 30 days ago: `trend_pct = 100 * trend_30_day / (market_value - trend_30_day)`.
  - If that base is 0 or less, skip the player.
  - The filter must use the same base (fallers: trend_pct below -25).
- Scope:
  - Show only players on Diego's roster or in the top 15 waiver targets, max 10 lines.
  - Put the top moves FIRST in both reports and the news check LAST.
- Tests:
  - V=37, trend=-181 gives about -83%.
  - A rising player with base <= 0 is skipped.
- Lesson to add to `LESSONS.md`: "Percent change uses the prior value as the base."

## Item 2: Waiver advice quality
Fix in `scripts/find_moves.py` and the waiver report:
1. One row per add: show the single best drop for each add (not six rows for the same player). Show the top 10 distinct adds.
2. Drop protection:
   - Never suggest dropping anyone with market V of 300 or more unless the playoff gain is at least +0.05.
   - Never suggest dropping an IR player with an expected return.
   - Dropping an IR player with V of 0 (out for the season) is fine.
3. Priority advice:
   - With rolling priority, using a claim sends Diego to the back of the line.
   - Say "worth using priority" only when the playoff gain is at least +0.03 and the add is a starter or has a bye-week starting role.
   - Otherwise say "depth only, skip".
   - Keep the pool-estimated warning whenever `available.txt` is missing or older than 7 days.
4. Estimated pool realism:
   - When the pool is estimated, give each synthetic team a K and a DEF drafted from the top projected players, so elite kickers are not free.
   - Keep the warning in place.
5. `available.txt` parsing:
   - When it exists and is under 7 days old, use ONLY those players as the free agent pool.
   - The file may contain several pasted Yahoo Players pages (one per position) one after another. Parse them tolerantly.
   - Format hints from real Yahoo text: `Tyrone TracyNew Player Note Sea - RB`, `A.J. BrownQNew Player Note NE - WR` (the Q is an injury tag stuck to the name), `Jordyn TysonIR-RPlayer Note NO - WR`, `BroncosNo new player Notes Den - DEF`.
   - List any unparsed lines in `logs/available_unparsed.log`.
6. Tests: a fake `available.txt` fixture with made-up names, plus one test each for the drop-protection and priority rules.

## Item 3: Yahoo loader safety (the API may be approved any day)
- `scripts/load_yahoo.py` has only been tested on a fake JSON file. It writes settings into `config.yaml`.
- Required changes:
  - Backup first: before any write, copy `config.yaml` to `config.yaml.pre-yahoo-<timestamp>`.
  - Merge, never replace: keys the API does not return (yardage milestones, 40+ yard bonuses, 4th-down stops, IDP scoring, `waiver_*`, `trade_deadline`, `playoff_reseeding`) must survive untouched.
  - Conflicts: if the API returns a value that differs from the pasted-settings value for a key, keep the existing value, and list the difference in `reports/yahoo_load_diff.md` for Diego to review.
  - Partial flag: set `partial_import: false` ONLY if rosters for all 12 teams, standings, and the schedule loaded. Otherwise keep it true.
  - Failure mode: any parsing error must leave `config.yaml` unchanged and print which table failed.
- Tests:
  - A fixture where the API payload omits milestones and 40+ bonuses; assert they remain after the load.
  - A fixture with a conflicting `pass_td`; assert it is kept and reported.
  - A fixture with a broken standings table; assert `config.yaml` is byte-identical afterward.

## Item 4: Explainer share bug
- Bug: in `scripts/explain_week.py` the Malik Nabers week 4 report shows snap share 6.1% and target share 2.3%. These are impossible for a WR1. The snap denominator is the sum of `offense_snaps` over every player on the team, which is about 11 times the real team snap count.
- Fix:
  - Use the nflverse snap-count `offense_pct` average over the prior weeks, or divide by the team's snaps per game.
  - Compute target share as player targets divided by team pass attempts over the same prior weeks.
- Tests: a WR1 fixture must give a snap share between 0.55 and 1.0 and a target share between 0.12 and 0.40.
- Rerun all 6 explainers in `reports/explain/` and list the old and new values in the summary.

## Item 5: Expected-bonus projection (the main accuracy item)
- Problem: Sleeper's projected stat lines cannot contain league bonuses, so rescored projections omit them.
  - Milestones: passing 300/350/400, rushing 50/100/150, receiving 100/150/200.
  - 40+ yard plays: completions, runs, receptions, and the TD versions.
  - Bias of actual minus projection in `reports/projection_scorecard.md` is positive: QB +1.2 to +2.8, RB +1.2, WR high bucket +1.2, DEF mid +4.4 (4th-down stops).
- Method (all past-only, walk-forward):
  - Yardage milestones:
    - For each position, fit the conditional distribution of actual yards given projected yards, using nearest-projection empirical residuals in the style of the existing quantile model.
    - Convert it to P(yards >= each threshold).
    - Expected milestone bonus = sum over tiers, using `milestone_mode` from `config.yaml` (`highest` by default). Compute BOTH modes, and report which mode `config.yaml` uses.
  - 40+ yard plays:
    - Estimate the expected count of 40+ plays per game as a function of projected yards for QB, RB, WR, TE (rate per projected yard by position, shrunk toward the position mean).
    - Multiply by the point values.
    - For TD versions, use the projected TD rate times the share of TDs that are 40+ historically.
  - DEF 4th-down stops: expected stops as a function of the opponent's 4th-down attempt rate and the team's historical stop rate (rolling, shrunk).
- New field: `proj_pts_bonus = rescored_proj + expected_bonus`.
- Preregister in `reports/experiments.md` BEFORE running:
  - Hypothesis: adding expected bonus points removes the known downward bias and improves accuracy.
  - Metrics: MAE and Spearman by position (adoption metrics), mean bias by position and projection bucket (diagnostic), and sample-weighted CRPS after refitting the quantile tables (diagnostic).
  - Adoption rule, set now because this corrects a known omission rather than searching for gains: adopt if MAE is not worse than baseline by more than 0.5% in any period, AND mean bias moves closer to zero in at least 5 of the 6 positions, AND Spearman is not worse in any period. Also report the standard 1% rule result.
  - Test periods: 2023, 2024, 2025, completed 2026 weeks.
- If adopted:
  - Set `projection_source: sleeper_bonus` in `config.yaml`.
  - Refit the quantile tables on the new projection, then rerun the calibration report and P6 worlds.
  - Report before and after for coverage, CRPS, and the league odds.
- If rejected: leave everything off and write the numbers.
- Tests: a hand-computed player with a projected 95 receiving yards must have an expected bonus between 0 and the maximum bonus; leakage check that the week-W bonus fit never touches week-W data.

## Item 6: Own-model features, properly
- Task 02's own model used only 4 inputs: Sleeper projection, last-3 average, season average, EWMA. Task 02 asked for more.
- Add the missing pregame features (past-only): snap share and target share (fixed per Item 4), carries share, team implied points and spread, opponent points allowed to the position (rolling, shrunk toward the league mean), home/away, and a QB-change flag.
- Models: ridge first. Try `HistGradientBoostingRegressor` only if ridge is finished and tested. Fixed seeds.
- Compare against the Item 5 projection when it exists, otherwise against Sleeper.
- Standard adoption rule. Preregister first.
- Time-box: 2 hours. If the standard rule is not met, record the numbers and stop.

## Item 7: Full-league paste import (do this ONLY if `.env` has no `YAHOO_CLIENT_ID`)
If the Yahoo API is configured, skip this item and say so in the summary.
- Extend `scripts/parse_yahoo_paste.py` to also read:
  - `team_01.txt` to `team_12.txt` (one roster page each; Diego's is `my_roster.txt`)
  - `standings.txt`
  - `schedule_wNN.txt` (matchups for each remaining regular-season week)
- Raw roster pages look like Item 2's format hints. Slot codes are QB, RB, WR, TE, W/R/T, K, DEF, D, BN, IR.
- The parser must be tolerant, and strict about failures:
  - List every unparsed or unmatched line in `logs/yahoo_paste_unparsed.log`.
  - If more than 3 players cannot be matched to Sleeper IDs, stop and list them under Needs Diego.
- When all 12 rosters, standings, and the schedule are present:
  - Replace the synthetic league with the real one.
  - Set `partial_import: false`.
  - Rebuild P6 worlds with the real schedule.
  - Rerun P8 and the waiver job.
  - Label outputs "real league".
- Tests: fake fixtures with made-up names only. Never use real pasted data in tests.

## Learning loop
- Append every failure, bug, or surprise to `LESSONS.md` (what happened, root cause, rule from now on).
- Also save the rule in your own memory or skill feature.
- Read `LESSONS.md` before each item.

## Finish
- Update `PROGRESS.md`.
- Write `reports/task04_summary.md` with:
  - each item's before and after numbers
  - what was adopted or rejected
  - the Item 4 old and new share values
  - the Item 5 bias table before and after
  - a "Needs Diego" list
- Send Diego a final Telegram message with the summary headline.
- Remind Diego to push from the host: `cd ~/.hermes/ff-model && git push`.
- If the whole task passes 8 hours, stop at a clean commit and write the summary with what is left.
