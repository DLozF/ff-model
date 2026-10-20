# Task 01: Import Diego's league settings and his own roster (partial import)

You are Chronos. Project root: `/opt/data/ff-model` (host: `~/.hermes/ff-model`).

## Before you start
1. This prompt is `tasks/01_league_import.md`. Commit it first if it is not committed.
2. Read `LESSONS.md`, `PROGRESS.md`, `README.md`, PLAN.md section A2, and `docs/YAHOO_SETUP.md` section 4 (CSV alternative). A2's rules apply.
3. Git: use branch `improve-2026-10` (create it from `overnight-2026-10-20` if missing). Never commit to `master`, never push.
4. Add `data/yahoo_paste/` and `data/league_csv/` to `.gitignore` before anything else. Never commit pasted pages or league member names.
5. Do not ask questions. Log assumptions in `PROGRESS.md`.

## Scope
- Yahoo API access is not approved yet. Diego will connect Yahoo later.
- For now, import only:
  - league settings
  - Diego's own roster
- The other 11 teams stay synthetic.
- Build this as a **partial import mode** so the full import (all teams, standings, schedule) can be added later without rework.

## Input
Diego copied Yahoo web pages as plain text into `/opt/data/ff-model/data/yahoo_paste/`:
- `my_team.txt`: his team name.
- `settings.txt`: the League > Settings page.
- `my_roster.txt`: his team's roster page.
- `available.txt` (optional, may be missing): the Players page filtered to Available.

The text is messy copy-paste. Expect menus, ads, stat columns, and injury tags like Q, D, O, IR, and NA.

`my_roster.txt` is already cleaned:
- `#` header lines hold the league info.
- The rest is a CSV with columns `slot,name,pos,nfl_team,bye,yahoo_status,yahoo_proj_w7,pct_start,pct_rostered`.
- Read it directly.

## Known league differences from the current config
Fix all of these. Confirm each value against `settings.txt`.

### Lineup
- The lineup is QB, 2 RB, 2 WR, TE, W/R/T (flex), K, DEF, **1 IDP slot (`D`)**, 6 bench, 2 IR.
- The model has no IDP support. Do not build it now. Treat the IDP starter (currently Kyle Hamilton, S) as a fixed weekly contribution: his Yahoo projection, or the league-average IDP if the projection is missing.
- Keep IDP out of trades and waivers. Note the limitation in the summary.

### Scoring: this is NOT standard PPR (confirmed in `settings.txt`)
- Pass TD 6 (config has 4). Interception -2 (config has -1). Offensive fumble return TD 6.
- Yardage milestone bonuses:
  - Passing: 2 at 300, 3 at 350, 4 at 400.
  - Rushing: 1 at 50, 2 at 100, 3 at 150.
  - Receiving: 1 at 100, 2 at 150, 3 at 200.
  - Yahoo's text does not say whether the tiers stack or only the highest tier counts. Implement both versions, log which one you used under Assumptions, and put "confirm bonus tiers" on the Needs Diego list.
- 40+ yard bonuses:
  - 40+ completion 1, 40+ pass TD 2.
  - 40+ run 1, 40+ rush TD 3.
  - 40+ reception 1, 40+ receiving TD 3.
  - Compute them from nflverse play-by-play by counting each player's 40+ yard plays per game.
- DEF extras:
  - 4th-down stops 2. Compute from play-by-play: an opponent 4th-down play that fails to convert, excluding punts and field goals.
  - Extra point returned 2. Kick and punt return TD 6.
  - Points allowed 21-27 is 0.
- IDP scoring is listed in `settings.txt`. Store it in `config.yaml` but do not model IDP (see Lineup).

### What the new scoring changes
- Sleeper's `pts_ppr` no longer matches the league.
  - Rescore every historical actual from raw stats plus play-by-play under league scoring.
  - Rescore every projection from Sleeper's projected stat lines (pass_yd, pass_td, rec, and so on) under league scoring. If `projection_records` only kept `pts_ppr`, re-cache the projections with full stat lines.
  - Milestone and 40+ bonuses can't come from a projected stat line. Leave them out of the projection; the refit residual quantiles will absorb their average. Report the mean residual per position after the refit to confirm it is near 0.
- Refit P3 quantiles, the P4 tables that depend on points, the P5 copula, and P6 worlds, all under league scoring.
- Rerun the calibration report and compare the before and after coverage tables.
- Add tests that score known stat lines by hand: a 320-yard, 3-TD passing game with one 45-yard TD; a 110-yard rushing game with a 42-yard run.

### Other settings
- Waivers: continual rolling list, 2-day waiver period, weekly waivers "Game Time - Tuesday". Set `waiver_type: rolling`. Diego is 8th in priority.
- Trade deadline is November 28, 2026. After that date, `find_moves.py` must skip trades and only report waivers.
- Playoffs: 6 teams, weeks 15-17, higher seed wins playoff ties, reseeding on. Make the season sim match.
- No draft pick trades, no trade review, no acquisition limits.

### IR slots
- Diego's 2 IR slots hold Jordyn Tyson and Dylan Sampson (both IR-R).
- Model them as unavailable until their return week.
- When they come back, the waiver finder must account for the roster spot they will take.

## Steps
1. **Write the parser.** Create `scripts/parse_yahoo_paste.py` with a `--partial` flag.
2. **Parse settings.**
   - Roster slots, bench size, IR slots, full scoring, playoff teams, playoff weeks, tiebreaker, and waiver type (FAAB budget or rolling priority).
   - Write the parsed values into `config.yaml`. Add `waiver_type` and `faab_budget`.
   - Any setting you cannot find keeps its current value and goes on the Needs Diego list. Never invent a value.
3. **Match Diego's roster to Sleeper IDs.**
   - Normalize names: case, punctuation, apostrophes, and suffixes (Jr., Sr., II, III).
   - Match on name plus position plus NFL team. Fall back to name plus position only if the team changed.
   - DEF: map to the Sleeper team abbreviation.
   - Write anything unresolved to `logs/yahoo_name_unmatched.log` and list it under Needs Diego. Never guess silently.
4. **Build the synthetic league around Diego's real team.**
   - Replace the synthetic `my_team` roster with Diego's real roster and use his real team name.
   - Re-draft the other 11 synthetic rosters from the remaining player pool, using the same FantasyCalc-V method as P6, so no player is on two teams.
5. **Free agents.**
   - If `available.txt` exists, parse it. It becomes the waiver pool, and the report header shows the pasted date.
   - If it is missing, the free agent pool is every player not on Diego's roster or a synthetic roster. Label all waiver output: "free agents are estimated; confirm on Yahoo before claiming".
6. **Rebuild and rerun.**
   - Rebuild P6 worlds from the current week.
   - Rerun P8 for waivers and trades.
   - Label trade ideas and league odds "synthetic opponents".
7. **Tests.** Add parser tests using a small fake paste fixture with made-up names in `tests/fixtures/`. Never use the real paste.

## Output
Write `reports/league_import_summary.md` with:
- Settings diff: old `config.yaml` values vs parsed values.
- Diego's roster with Sleeper ID and match method for each player.
- Unmatched players.
- Diego's playoff odds (synthetic opponents).
- Diego's optimal lineup this week.
- Top 5 waiver moves.
- Needs Diego list.

## Learning loop
- Append any failure, bug, or surprise to `LESSONS.md`: what happened, root cause, and the rule from now on.
- Also save the rule in your own memory or skill feature, if you have one.

## Finish
- Update `PROGRESS.md`.
- Commit once per step, with `scripts/check.sh` passing before each commit.
