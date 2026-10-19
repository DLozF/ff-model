# Yahoo setup

## 1. Get Yahoo Fantasy API read access

As of October 2026, Yahoo manually reviews Fantasy Sports API access. Creating a normal Yahoo developer app alone is not sufficient.

1. Apply for read-only Fantasy Sports API access at `https://sports.yahoo.com/developer/access/`.
2. Describe this as a personal, single-league fantasy-football decision model. Requested data: league settings, scoring, rosters, free agents, standings, and matchups. Expected users: 1.
3. Complete Yahoo's API Access and Use Agreement and any confirmation form Yahoo sends.
4. After approval, create or update an app in the Yahoo Developer Network and confirm that **Fantasy Sports – Read** appears under API Permissions.
5. Set the redirect URI to `https://localhost:8080`.
6. Copy the app's Client ID and Client Secret.

Yahoo's current portal and documentation:
- `https://sports.yahoo.com/developer/`
- `https://sports.yahoo.com/developer/docs/`

## 2. Configure the project

On the OptiPlex host, edit the project `.env`:

```bash
nano ~/.hermes/ff-model/.env
```

Add:

```dotenv
YAHOO_CLIENT_ID=<Client ID>
YAHOO_CLIENT_SECRET=<Client Secret>
YAHOO_LEAGUE_ID=<numeric league ID>
```

Do not commit `.env`.

## 3. First login from Docker

Run this exact command over SSH on the OptiPlex:

```bash
docker exec -it chronos bash -lc 'cd /opt/data/ff-model && PYTHONPATH=src /tmp/ff-venv/bin/python scripts/load_yahoo.py'
```

If `/tmp/ff-venv` disappeared after a container restart, rebuild it first:

```bash
docker exec -it chronos bash -lc 'UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python /usr/local/bin/uv venv /tmp/ff-venv --python 3.12 && UV_CACHE_DIR=/tmp/uv-cache UV_PYTHON_INSTALL_DIR=/tmp/uv-python /usr/local/bin/uv pip install --python /tmp/ff-venv/bin/python -r /opt/data/ff-model/requirements.txt'
```

The OptiPlex has no browser. YFPY will print an authorization URL instead of opening one. Open that URL on a laptop or phone, sign into the Yahoo account that owns the league, approve access, and paste the verification code into the Docker terminal prompt.

The loader uses `save_token_data_to_env_file=True` with `/opt/data/ff-model/.env`. YFPY saves `YAHOO_ACCESS_TOKEN_JSON` there, so later runs reuse and refresh the token.

Successful output says that normalized Yahoo tables were cached and `config.yaml` was updated. Files are written as `data/cache/yahoo_*.parquet`; settings are written to `data/cache/yahoo_settings.json`.

## 4. CSV alternative

If API approval is unavailable, prepare a directory with:

- `league.csv`: one row containing `teams,current_week,bench,regular_season_weeks,playoff_teams,playoff_weeks`
- `lineup.csv`: `position,count`
- `scoring.csv`: `config_key,value`
- `teams.csv`: `team_id,team_name`
- `rosters.csv`: `team_id,team_name,yahoo_id,sleeper_id,name,pos,team`
- `free_agents.csv`: `yahoo_id,sleeper_id,name,pos,team`
- `standings.csv`: `team_id,wins,losses,ties,points_for,rank`
- `schedule.csv`: `week,team1_id,team2_id`

Then run:

```bash
docker exec -it chronos bash -lc 'cd /opt/data/ff-model && PYTHONPATH=src /tmp/ff-venv/bin/python scripts/load_yahoo.py --csv-dir /absolute/path/to/csv-directory'
```
