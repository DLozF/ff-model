# FF-Model Overnight Build Plan (instructions for Chronos)

This file is your complete instructions for tonight.
- Read PART A now, all of it.
- For PART B, read only the phase you are on. Find phase line numbers with `grep -n "^## " /opt/data/ff-model/PLAN.md`, then read just that range.
- Re-read your current phase before starting it, and again after any context compression.

---

# PART A: Mission, environment, rules

## A1. Mission
- Build a Python decision model for Diego's Yahoo fantasy football league: 12 teams, full PPR, lineup QB, 2 RB, 2 WR, TE, FLEX (RB/WR/TE), K, DEF.
- The model answers one question: does a trade or waiver move raise Diego's probability of making the playoffs and winning the title? Not "who won the trade."
- Tonight: build and validate everything that does not need a Yahoo login, using real NFL data and a synthetic 12-team league. Diego connects Yahoo in the morning.
- Core design:
  1. Simulate the NFL many times ("worlds"): who plays, and how many fantasy points each player scores, for every remaining week.
  2. Evaluate any set of fantasy rosters against the same saved worlds.
  3. Before and after a trade use identical worlds (common random numbers), so trade deltas are precise and cheap to compute.

## A2. Environment
- You are Chronos, in the `chronos` Docker container on Diego's homelab (an Ubuntu OptiPlex). Your terminal tool may have a minimal PATH, so always use absolute paths.
- Hardware: 2 CPU cores and 7.5 GB RAM, shared with Diego's Immich photo server. Keep the build under about 2 GB of RAM and run one heavy job at a time.
- Project root: `/opt/data/ff-model` (on the host: `~/.hermes/ff-model`).
- `/opt/data` is your home folder. It also holds your own config and Diego's other jobs (internwatch and others). Only create or change files inside `/opt/data/ff-model`.
- Python tooling is `uv`.
  - Find it with `command -v uv`. If it is missing, install it into /tmp: `curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/tmp/uv-bin UV_NO_MODIFY_PATH=1 sh`, then use `/tmp/uv-bin/uv`. Below, `uv` means the full path you found.
  - Start every uv command with `UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python` so uv writes nothing into `/opt/data`.
- Virtual env: `/tmp/ff-venv` (inside the container, rebuildable).
  - Create: `UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python uv venv /tmp/ff-venv --python 3.12`
  - Install: `UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python uv pip install --python /tmp/ff-venv/bin/python -r /opt/data/ff-model/requirements.txt`
  - Run tests: `cd /opt/data/ff-model && /tmp/ff-venv/bin/python -m pytest -q`
  - If `/tmp/ff-venv` is ever missing (container restart), rebuild it the same way.
- Large simulation arrays go in `/tmp/ff-worlds/`, never inside the project folder.
- Anything that may run longer than 2 minutes: run it in the background with output to a log (`nohup <cmd> > logs/<name>.log 2>&1 &`), then poll with `tail -n 20 logs/<name>.log`.
- Clock: `TZ=America/Chicago date`. Do not start a new phase after 22:00 Central. MORNING_REPORT.md must exist by 23:00 Central.

## A3. Rules
1. Diego is asleep. Never ask questions. Choose the simplest reasonable option and log it under "Assumptions" in PROGRESS.md.
2. Work alone in this one session. No subagents, no delegation. Track each phase (P0 to P11) in the Status table in PROGRESS.md: not started, in progress, done, or blocked.
3. Small steps: one module (under 250 lines) plus its test, run it, fix it, move on. Concise code, one-line docstrings, no comments that restate the code. Use your patch/edit tool for small changes instead of rewriting whole files.
4. Inspect before coding: for each new dataset, print its columns and 3 rows once, record the columns in `docs/data_schema.md`, then code against the real names. Never guess column names or JSON keys.
5. Short tool output: `pytest -q`; long output goes to `logs/<name>.log` and you read only `tail -n 30`. Never print whole DataFrames or arrays.
6. Cache every download as Parquet in `data/cache/`. Never download the same thing twice. Delete raw JSON after converting.
7. APIs: at most 2 requests per second to Sleeper, retry with backoff, give up on a source after 5 failures in a row.
8. Three strikes: if the same error survives 3 fix attempts, log it under "Blocked" in PROGRESS.md and continue with the next phase that does not depend on it.
9. A phase is done only when its DONE WHEN checks were actually run and passed. Paste the check results (max 10 lines) into PROGRESS.md.
10. No invented numbers. Every number in any report must come from a file a script produced.
11. Vectorize over worlds with NumPy (no Python loops over worlds), float32 arrays. Use `n_dev` worlds while developing and `n_final` only for final checks.
12. No data leakage. To evaluate season S or week w, fit only on data from before it.
13. Do not attempt a Yahoo login. Do not touch anything outside `/opt/data/ff-model` and your `/tmp` folders (ff-venv, ff-worlds, uv). Never change your own config, your scheduled jobs, or Diego's other jobs. Do not install packages beyond requirements.txt without logging why.
14. After each phase: run all tests, update PROGRESS.md (its Status row, plus max 15 lines per phase), `git commit` if git exists.
15. All randomness uses the seed from config.yaml, so every result can be reproduced.

## A4. Project layout
```
ff-model/
  PLAN.md  PROGRESS.md  MORNING_REPORT.md  config.yaml  requirements.txt  .gitignore  .env.example
  data/cache/            # parquet only
  models/                # fitted parameters (json, npz)
  reports/               # markdown outputs
  logs/
  docs/data_schema.md  docs/YAHOO_SETUP.md
  src/ffm/
    config.py  ids.py  sleeper.py  nfl.py  scoring.py  dataset.py
    lineup.py  distributions.py  availability.py  qb.py  copula.py
    worlds.py  league.py  season.py  trade.py  finder.py  waivers.py
    backtest.py  yahoo_loader.py  report.py
  scripts/               # thin command-line entry points
  tests/
```
`.gitignore`: `.env`, `data/cache/`, `logs/`, `*.npy`

## A5. config.yaml (create exactly; VERIFY values get replaced from Yahoo in the morning)
```yaml
league:
  teams: 12
  my_team: "Team 1"                 # synthetic league until Yahoo is connected
  lineup: {QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DEF: 1}
  flex_eligible: [RB, WR, TE]
  bench: 6                          # VERIFY
  regular_season_weeks: [1, 14]     # VERIFY
  playoff_teams: 6                  # VERIFY
  playoff_weeks: [15, 16, 17]       # VERIFY
  tiebreaker: points_for
scoring:                            # VERIFY against Yahoo settings
  pass_yd: 0.04
  pass_td: 4
  pass_int: -1
  pass_2pt: 2
  rush_yd: 0.1
  rush_td: 6
  rush_2pt: 2
  rec: 1.0
  rec_yd: 0.1
  rec_td: 6
  rec_2pt: 2
  fum_lost: -2
  ret_td: 6
  xpm: 1
  fgm_0_19: 3
  fgm_20_29: 3
  fgm_30_39: 3
  fgm_40_49: 4
  fgm_50p: 5
  def_sack: 1
  def_int: 2
  def_fum_rec: 2
  def_td: 6
  def_safety: 2
  def_blk_kick: 2
  def_pts_allowed: {"0": 10, "1-6": 7, "7-13": 4, "14-20": 1, "21-27": 0, "28-34": -1, "35+": -4}
sim:
  seed: 2026
  n_dev: 1000
  n_final: 5000
  training_seasons: [2021, 2022, 2023, 2024, 2025]
  current_season: 2026
paths:
  root: /opt/data/ff-model
  venv: /tmp/ff-venv
  worlds: /tmp/ff-worlds
```

## A6. requirements.txt
`nflreadpy polars pyarrow pandas numpy scipy scikit-learn pulp pyyaml requests python-dotenv yfpy pytest` (one per line)

## A7. Data sources
- Sleeper (no key needed). Probe each URL once and record the response shape before writing loaders.
  - Projections: `https://api.sleeper.app/projections/nfl/{season}/{week}?season_type=regular&position[]=QB&position[]=RB&position[]=WR&position[]=TE&position[]=K&position[]=DEF`
    - Fallback: `https://api.sleeper.app/v1/projections/nfl/regular/{season}/{week}`
  - Actual stats: `https://api.sleeper.app/v1/stats/nfl/regular/{season}/{week}`
    - Fallback: `https://api.sleeper.app/stats/nfl/{season}/{week}?season_type=regular&position[]=QB&position[]=RB&position[]=WR&position[]=TE&position[]=K&position[]=DEF`
  - Players (names, teams, `injury_status`): `https://api.sleeper.app/v1/players/nfl` (large, download once per run)
  - Current season and week: `https://api.sleeper.app/v1/state/nfl`
- nflverse via `nflreadpy` (returns Polars; convert with `.to_pandas()`): `load_schedules`, `load_player_stats` (weekly), `load_injuries`, `load_snap_counts`, `load_ff_playerids` (maps sleeper_id, yahoo_id, gsis_id), `load_ff_opportunity`.
  - `load_ff_opportunity` uses each game's real opportunities. Only use it as a feature from past weeks, never as a same-week projection.
- Seasons: training 2021 to 2025. Current season 2026, fully completed weeks only. A week is complete only when every game in it has a final score in `load_schedules`.
- Team abbreviations differ between sources (for example LA vs LAR). Build one mapping in `ids.py` and test that it covers all 32 teams.

---

# PART B: Phases (priority order; each one leaves working, tested code)

## P0. Setup
1. Create the folder layout, config.yaml, requirements.txt, .gitignore, .env.example (YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET, YAHOO_LEAGUE_ID), and PROGRESS.md with sections: Status (one row per phase, P0 to P11, all "not started"), Assumptions, Blocked, Log.
2. Find or install uv, then build the venv and install requirements (A2).
3. `git init` if git exists.
4. `src/ffm/config.py`: load config.yaml into a dict; one test.

DONE WHEN: `pytest -q` passes, and `/tmp/ff-venv/bin/python -c "import nflreadpy, pulp, polars"` works.

## P1. Data and scoring
1. Probe the Sleeper URLs (one request each, season 2025 week 5). Record keys in docs/data_schema.md. Check whether 2026 projections exist for weeks after the current week, and record the answer in PROGRESS.md.
2. Download Sleeper projections and actual stats for 2021 to 2025 weeks 1 to 18, plus 2026 completed weeks. Download 2026 projections for every remaining week that has data.
3. Download the nflverse datasets for 2021 to 2026.
4. `scoring.py`: fantasy points from a stat line using config.scoring. Map Sleeper stat keys to config keys only after inspecting real keys. DEF points-allowed tiers use Sleeper's points-allowed fields. Kickers: map Sleeper's distance buckets onto the config buckets (50 yards or longer counts as fgm_50p).
5. `dataset.py`: one table `player_weeks` with season, week, sleeper_id, gsis_id, name, pos, team, opp, proj_pts, act_pts, played (true if the player appears in the actual stats or has snaps > 0). Keep rows with proj_pts >= 0.5 or act_pts != 0.
6. Fallback, only if Sleeper historical projections are unavailable: baseline projection = 0.5 x exponentially weighted mean of the player's prior fantasy points (half-life 3 games) + 0.5 x the same average of his prior expected fantasy points from load_ff_opportunity. Past weeks only. Log loudly that the fallback is in use.

DONE WHEN:
- For QB/RB/WR/TE rows, points recomputed with config.scoring match Sleeper's `pts_ppr` within 0.5 for at least 95% of rows. If not, inspect the 20 largest mismatches to find the mis-mapped stat.
- `player_weeks` has more than 20,000 training-season rows.
- The team-map test passes.

## P2. Lineup optimizer
- `lineup.py` with two solvers:
  - `greedy(proj, pos, avail)`: vectorized over worlds. Fill QB, RB x2, WR x2, TE, K, DEF with the highest projections among available players, then FLEX with the best remaining RB/WR/TE. Greedy is optimal for this lineup shape.
  - `pulp_lineup(...)`: integer program, used only as a reference in tests.
- Lineups are chosen from projections (what the manager sees before kickoff), never from simulated scores.

DONE WHEN: greedy equals PuLP total projected points (difference below 1e-6) on 1,000 random rosters; tests pass for a bye week, an injured starter, and FLEX choosing the best leftover RB/WR/TE.

## P3. Score distribution model (the most important statistics)
Goal: for a player who plays, the full distribution of fantasy points given his projection and position.
1. Training rows: played == true, by position.
2. Quantile levels: u = 0.005, 0.010, ..., 0.995 (199 levels).
3. Projection grid per position: 0 to the 99.5th percentile of proj_pts, step 0.25.
4. For each grid point p: take the K = 300 training rows with the closest proj_pts; compute quantiles r_u of the residual (act_pts minus proj_pts); set Q(u | p) = max(floor_pos, p + r_u), where floor_pos = the 0.1th percentile of act_pts for that position.
5. Clean-up: make Q non-decreasing in u (running maximum); smooth across p with a centered rolling mean over 5 grid points; enforce non-decreasing in u again. For p above the grid, scale the top row's residuals by p / p_max.
6. Sampling: points = Q(u | p) with linear interpolation in p and in u. u comes from the copula in P5 (uniform random until then).
7. Backtest, rolling by season: fit on seasons before S, test on S, for S = 2023, 2024, 2025, and 2026 completed weeks (fit on 2021 to 2025).
   - Metrics per position: MAE of the median vs actual; coverage of the 50%, 80%, 95% central intervals; CRPS from quantiles = (2 / 199) x sum over levels of pinball_loss(u, actual, Q_u); 10-bin PIT histogram.
   - Baseline to beat: Normal(proj_pts, sigma_pos), sigma_pos = residual standard deviation by position from the same training data.
8. Save tables to `models/quantiles_<last_fit_season>.npz`, results to `reports/calibration.md`.

DONE WHEN: every position's coverage is within 3 percentage points of nominal in every test season, and CRPS beats the Normal baseline in every test season. If a position misses, retry once with K = 500 and smoothing width 9 before logging it.

## P4. Availability and QB effect
1. Weekly availability as a two-state Markov chain per position (Healthy, Out):
   - h_pos = P(misses week t+1 | played week t); r_pos = P(plays week t+1 | missed week t).
   - Estimate from 2021 to 2025 for players averaging proj_pts >= 5, skipping team bye weeks and weeks before a player's first or after his last appearance in a season.
   - Separate r_IR for players on injured reserve (from load_injuries or Sleeper status).
2. Next-week play probability by injury report status (Out, Doubtful, Questionable, none): match load_injuries rows to whether the player played that week.
3. QB effect (the JSN/Darnold and Olave/Shough effect):
   - QB1 = highest projected QB on a team that week.
   - kappa = average of (backup QB's points in his starts) / (the injured starter's projection in his last healthy week). Default 0.75 if fewer than 30 cases.
   - beta_pos for WR, TE, RB: regress (player's average points with the backup / his average with the starter, same season) minus 1, on (kappa for those games) minus 1. Defaults if fewer than 30 cases at that position: WR 0.6, TE 0.6, RB 0.3. Record sample sizes.
4. Save `models/availability.json` and `models/qb_effect.json`.

DONE WHEN: files saved with sample sizes, and sanity checks pass: 0.01 < h_pos < 0.2, 0.1 < r_pos < 0.9, P(play | Out) < 0.05, 0.5 < P(play | Questionable) < 0.95. If a check fails, use the default, log it under Assumptions, and continue.

## P5. Correlation (Gaussian copula)
Goal: teammates and opponents rise and fall together the way they really do.
1. For each played training row: u = F(act_pts | proj_pts, pos) from the P3 tables (interpolate), z = inverse_normal(clip(u, 0.001, 0.999)).
2. Slots per team-week, ranked by projection among players who played: QB1, RB1, RB2, WR1, WR2, WR3, TE1, K, DEF (9 slots).
3. One 18-dimensional vector per team-game: 9 own slots then 9 opponent slots. Use both orientations of every game.
4. Pairwise correlation matrix with pairwise-complete rows, NaN set to 0. Make the own-own and opp-opp blocks identical (average them); make the own-opp block symmetric.
5. Repair and shrink: eigen-decompose, clip eigenvalues at 1e-4, rescale to unit diagonal, then Sigma = 0.9 x Sigma + 0.1 x I. Save `models/copula.npz` with Sigma and pair counts.
6. Simulation use: per world, week and game, draw an 18-dim normal with the Cholesky factor. Every QB on a team uses the QB1 slot value (only one QB plays). Players outside the slots get independent normals. u = normal_cdf(z).

DONE WHEN: Sigma is positive definite; same-team QB1-WR1 correlation is positive; on held-out 2025, ratio = realized variance of (QB1 + WR1 + TE1 stack total minus its simulated mean) / average simulated variance is between 0.85 and 1.15. Record the same ratio for the independent version (Sigma = I) too.

## P6. World simulator and season simulator (synthetic league)
1. Current week W0 = first 2026 week that is not complete. Remaining weeks = W0 to the last playoff week.
2. Weekly projections for each remaining week: Sleeper's when available; otherwise a 3:2:1 weighted average of the player's three most recent weekly projections. Bye weeks = 0 (from load_schedules).
3. Player set: the top 450 by rest-of-season projected points, plus every QB on every NFL team, plus every rostered player.
4. `worlds.py`, for each remaining week, vectorized over N worlds:
   1. Availability: W0 state from `injury_status` in the Sleeper players file and the P4 step 2 probabilities; later weeks from the Markov chain. Bye = 0.
   2. Starting QB per team per world: QB1 if available, else the next available QB.
   3. proj_seen: if a backup starts, his projection = kappa x QB1's projection, and that team's WR/TE/RB projections are multiplied by 1 - beta_pos x (1 - kappa).
   4. Latent z from the copula per game, u = normal_cdf(z).
   5. points = available x Q(u | proj_seen).
   6. Save points (float32), available (bool), proj_seen (float32) as `.npy` in `/tmp/ff-worlds/2026_w{W0}/`, plus a player index parquet.
5. `league.py`: synthetic 12-team league. Snake draft by value over replacement: rest-of-season points minus the replacement player's points at that position (replacement = the player ranked 12 x starters at that position, with FLEX spots split evenly over RB/WR/TE). Teams fill starters before bench; 1 K and 1 DEF per team; 15 players per team. Free agents = undrafted players. Round-robin weekly schedule. Standings start at 0-0.
6. `season.py`, vectorized over worlds:
   - Each week each team starts its greedy lineup from proj_seen among available players; team score = sum of lineup points.
   - Head-to-head wins (ties = half a win), standings, tiebreaker points for.
   - Playoffs: fixed seeded bracket over the playoff weeks; top seeds get byes when playoff_teams is not a power of 2. For 6 teams over 3 weeks: week 1 is 3v6 and 4v5; week 2 is 1 v winner(4,5) and 2 v winner(3,6); week 3 is the final.
   - Outputs per team: P(playoffs), P(bye), P(champion), expected wins, expected points for.
7. `reports/league_odds.md`: table of all 12 synthetic teams.

DONE WHEN: in every world exactly playoff_teams teams make the playoffs (sum of P(playoffs) equals playoff_teams within 1e-9); P(champion) sums to 1; rerunning with the same seed gives identical numbers; an n_final run (worlds + season) finishes in under 10 minutes (log the time).

## P7. Trade evaluator
1. Input: `scripts/evaluate_trade.py --team "Team 5" --give "Name A,Name B" --get "Name C"`. Fuzzy-match names (difflib) and print the matched names.
2. Roster limits:
   - WELP = world-expected lineup points: mean over the first n_dev saved worlds of total starting lineup points across all remaining weeks.
   - Too many players: drop the player whose removal costs the least WELP.
   - Too few (the side giving 2 for 1): add the free agent who raises WELP the most, choosing from the top 5 free agents per position.
3. Run the season simulation for the before and after leagues on the same saved worlds (common random numbers).
4. For each metric Y (playoffs 0/1, champion 0/1, wins, missed playoffs 0/1): D_s = Y_after,s - Y_before,s; mean, SE = sd(D) / sqrt(N), 90% interval = mean +/- 1.645 x SE.
5. Report `reports/trade_<date>_<slug>.md`:
   - Both teams: change in P(playoffs), P(champion), expected wins, P(missing playoffs), each with its 90% interval.
   - Week-by-week starting lineup points before vs after (mean over worlds), split into regular season and playoff weeks.
   - QB exposure: share of Diego's expected lineup points tied to each NFL team's QB1, before vs after.
   - Verdict: if Diego's P(playoffs) before is above 90%, judge on P(champion), otherwise on P(playoffs). ACCEPT if the interval is entirely above 0, DECLINE if entirely below 0, else NO CLEAR EFFECT.
   - Acceptance: LIKELY if the other team's P(playoffs) rises, POSSIBLE if it drops by less than 1 percentage point, UNLIKELY otherwise.

DONE WHEN: an empty trade gives every delta exactly 0; trading a player for a clone with identical projections and identical world draws gives NO CLEAR EFFECT; a lopsided trade (Diego's worst bench player for the other team's best RB) gives ACCEPT; a sample report file exists.

## P8. Trade finder and waiver evaluator
1. Finder: every 1-for-1, 2-for-1 and 1-for-2 trade between Diego's team and each other team.
   - Screen: compute the WELP change for both teams; keep trades where Diego's WELP rises and the other team's does not fall.
   - Confirm the top 30 by Diego's WELP gain with the full trade evaluator.
   - Final list: trades with Diego's verdict ACCEPT and acceptance LIKELY or POSSIBLE, ranked by Diego's gain in the verdict metric. Save `reports/trade_ideas_<date>.md`.
2. Waivers: each of the top 40 free agents by rest-of-season points x each droppable player on Diego's roster. Screen by WELP, confirm the top 10 with the full evaluator. Save `reports/waivers_<date>.md`.

DONE WHEN: the finder finishes in under 20 minutes on the synthetic league and both reports exist.

## P9. Matchup calibration backtest
1. Test seasons 2024 and 2025, models fit only on earlier seasons.
2. Per week: 300 random legal lineup pairs from players who played (QB proj >= 12, RB/WR >= 6, TE >= 4, any K and DEF), plus 100 pairs where lineup A stacks a QB with his WR1.
3. For each pair: predicted P(A beats B) from 2,000 single-week worlds conditioned on players who played (this tests the score model and copula, not availability), then the real outcome.
4. Compare copula vs independent: Brier score, log loss, 10-bin calibration table, overall and for stacked pairs. Save `reports/matchup_calibration.md`.

DONE WHEN: the copula's Brier score is at most the independent Brier score, overall and for stacked pairs, and the worst calibration bin is within 5 percentage points.

## P10. Yahoo loader (write and test the code; do not log in)
1. `yahoo_loader.py` using yfpy: reads YAHOO_CLIENT_ID, YAHOO_CLIENT_SECRET, YAHOO_LEAGUE_ID from `.env`; pulls league settings and scoring (writes them into config.yaml, replacing VERIFY values), all rosters, free agents, weekly schedule, standings, current week.
2. Map Yahoo player IDs to Sleeper IDs with load_ff_playerids (yahoo_id to sleeper_id). DEF by team abbreviation.
3. CSV import alternative that produces the same tables.
4. `docs/YAHOO_SETUP.md`: step-by-step app registration (Fantasy Sports read permission, redirect URI `https://localhost:8080`) and first login. The OptiPlex has no browser: inside Docker, yfpy prints the authorization URL instead of opening one, so Diego opens it on his laptop or phone and pastes the verification code back. Give the exact command he runs over SSH on the OptiPlex (`docker exec -it chronos ...`). Save the token to the project's `.env` (yfpy: `save_token_data_to_env_file=True` with `env_file_location`) so later runs reuse it.
5. Make `league.py` load the real league from these tables instead of the synthetic draft, with real current standings.

DONE WHEN: a unit test that feeds saved fake Yahoo JSON through the loader produces correct rosters and settings.

## P11. Experiments (only if time remains)
Adopt a change only if it lowers out-of-sample CRPS by at least 1% in at least 2 of 3 test seasons. Otherwise leave it switched off in config. Record every result in `reports/experiments.md`.
- E1 Slow consensus: does a player's mean residual over his last 3 games predict his next residual? Fit k by least squares on training seasons; adjusted projection = proj + k x clip(mean_residual_last3, -3, 3).
- E2 QB efficiency: for WR and TE, add g x (z-scored EPA per dropback of the team's QB over his last 4 games). EPA per dropback = passing EPA / (attempts + sacks), from load_player_stats (inspect the column names first).
- E3 Matchup (only if Sleeper had no future-week projections): opponent effect = average residual the defense allowed to that position this season, shrunk by n / (n + 6) where n = games; applied to future-week projections.

---

# Morning report (write MORNING_REPORT.md, under 80 lines, using this template)
```
# Morning report: <date>
## Status
| Phase | Status (done / partial / blocked / not started) | Key result |
## Key numbers
- Distribution calibration per position (50/80/95 coverage) and CRPS vs Normal baseline
- Copula: QB1-WR1 correlation; stack variance ratio, copula vs independent
- Matchup calibration: Brier copula vs independent; worst bin error
- n_final worlds + season runtime
## Synthetic league odds (table)
## Sample trade report (one, trimmed)
## Assumptions I made
## Blocked or failed (exact error, what I tried)
## What Diego needs to do
1. Replace VERIFY values in config.yaml with the Yahoo league settings (or let the Yahoo loader do it).
2. Register the Yahoo app and log in once from the OptiPlex terminal (docs/YAHOO_SETUP.md).
3. <anything else>
## Next phases to run
```
