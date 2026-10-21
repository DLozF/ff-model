# Fantasy model automation

The jobs run entirely inside the `chronos` container. They use cached/model data and Python only; they do not make LLM calls.

## Install the host crontab

Run `crontab -e` on the OptiPlex host and add these exact lines:

```cron
CRON_TZ=America/Chicago
0 7 * * * docker exec chronos bash -lc '/opt/data/ff-model/scripts/run_job.sh daily'
0 10 * * 0 docker exec chronos bash -lc '/opt/data/ff-model/scripts/run_job.sh daily'
30 7 * * 2 docker exec chronos bash -lc '/opt/data/ff-model/scripts/run_job.sh waivers'
```

Schedule:

- `daily`: every morning at 7:00 AM Central.
- Sunday extra `daily`: 10:00 AM Central, before the main kickoff window.
- `waivers`: Tuesday at 7:30 AM Central. It runs the daily workflow first, rebuilds the upcoming-week worlds, and then produces the waiver report.

Do not add a separate Tuesday exception to the daily line. The `/tmp/ff-job.lock` lock prevents overlap; if the 7:00 job is still running at 7:30, the waiver job exits non-zero and writes a failure report instead of running concurrently.

## Manual runs

```bash
docker exec chronos bash -lc '/opt/data/ff-model/scripts/run_job.sh daily'
docker exec chronos bash -lc '/opt/data/ff-model/scripts/run_job.sh waivers'
```

Cached dry runs make no network requests:

```bash
docker exec chronos bash -lc '/opt/data/ff-model/scripts/run_job.sh daily --dry-run'
docker exec chronos bash -lc '/opt/data/ff-model/scripts/run_job.sh waivers --dry-run'
```

## Outputs

Daily:

- `/opt/data/ff-model/reports/daily_latest.md`
- `/opt/data/ff-model/reports/daily/daily_<YYYY-MM-DD>.md`
- `/opt/data/ff-model/reports/injuries/needs_review.md`

Waivers:

- `/opt/data/ff-model/reports/waivers_latest.md`
- `/opt/data/ff-model/reports/waivers/waivers_<YYYY-MM-DD>.md`

`needs_review.md` contains proposed long-term injury overrides. Review it manually; the job never edits `overrides.yaml`.

## Logs and failures

Logs are retained for 30 days:

- `/opt/data/ff-model/logs/daily_<YYYY-MM-DD>.log`
- `/opt/data/ff-model/logs/waivers_<YYYY-MM-DD>.log`

Check today's logs from the host:

```bash
docker exec chronos bash -lc 'tail -n 100 /opt/data/ff-model/logs/daily_$(TZ=America/Chicago date +%F).log'
docker exec chronos bash -lc 'tail -n 100 /opt/data/ff-model/logs/waivers_$(TZ=America/Chicago date +%F).log'
```

A failed job writes the last 40 log lines to one of:

- `/opt/data/ff-model/reports/JOB_FAILED_daily.md`
- `/opt/data/ff-model/reports/JOB_FAILED_waivers.md`

Check both from the host:

```bash
docker exec chronos bash -lc 'for f in /opt/data/ff-model/reports/JOB_FAILED_*.md; do [[ -e "$f" ]] && { echo "=== $f ==="; cat "$f"; }; done'
```

The relevant failure file is deleted automatically after the next successful run.

## Concurrency and resource controls

- `scripts/run_job.sh` holds `/tmp/ff-job.lock` with non-blocking `flock`; two jobs never overlap.
- Python job processes run under `nice -n 10` so Immich remains responsive.
- Any command failure produces a non-zero job exit.
- Runtime budgets: daily under 10 minutes; waivers under 15 minutes.
