# Overnight summary: 2026-10-20

## Run status
- Chronos received `OVERNIGHT.md` at 07:23 Central, after the 07:00 cutoff for starting new experiments and seven minutes before the 07:30 reporting deadline.
- Safety setup completed: tag `pre-overnight-2026-10-20` and branch `overnight-2026-10-20` were created. Nothing was pushed.
- The queue was not started because a baseline refresh alone has a 15-minute allowance and could not finish before the hard reporting deadline.

## Before vs after
| Metric | Before | After |
|---|---:|---:|
| Coverage and CRPS | Not re-baselined | Unchanged |
| Matchup Brier | Not re-baselined | Unchanged |
| Copula stack ratio | Not re-baselined | Unchanged |
| P6 runtime | 18.526s from prior verified run | 19.513s after Hurts override |
| P8 runtime | 473.502s from prior verified run | 466.183s after Hurts override |
| Tests | 53 passed from prior verified run | 54 passed after override support |

`reports/baseline_overnight.json` was not created because its required data refresh and validation were not run. No numbers were invented.

## Adopted changes
- None; no experiments were started after the cutoff.

## Rejected or timed-out experiments
- None; A1-D3 were not started because of the clock safety rule.

## Bugs found and fixed
- None during this abbreviated run.

## Needs Diego
- No Jalen Hurts input remains pending; he is overridden out for the rest of the season.
- Re-run these instructions before 07:00 Central to execute the full queue.
- D1 was not implemented, so there is no safe cron line to install yet.

## Morning commands
- Review branch: `cd /opt/data/ff-model && git diff master...overnight-2026-10-20`
- Merge after review: `cd /opt/data/ff-model && git checkout master && git merge overnight-2026-10-20`
- Roll back to the safety tag: `cd /opt/data/ff-model && git reset --hard pre-overnight-2026-10-20`
- Cron: none; `scripts/daily_snapshot.py` was not created, so do not schedule it.
