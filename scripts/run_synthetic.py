import json
import time
from pathlib import Path

import numpy as np
import polars as pl

from ffm.config import load_config
from ffm.distributions import QuantileModel
from ffm.ids import normalize_team
from ffm.league import partial_synthetic_league
from ffm.market import load_market, write_model_vs_market
from ffm.market_fallback import apply_model_fallback
from ffm.scoring import score_projection_frame
from ffm.season import roster_team_scores, simulate_team_scores
from ffm.worlds import (
    generate_worlds,
    load_injury_overrides,
    weighted_recent_projection,
    write_world_manifest,
)

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"
VALID_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DEF"}


def completed_weeks(schedules, season):
    """Return completed regular-season weeks."""
    regular = schedules.filter((pl.col("season") == season) & (pl.col("game_type") == "REG"))
    grouped = regular.group_by("week").agg(
        (pl.col("home_score").is_not_null().all() & pl.col("away_score").is_not_null().all()).alias("complete")
    )
    return sorted(grouped.filter("complete").get_column("week").to_list())


def load_projection_history(season, scoring):
    """Load compact cached projections for one season."""
    frames = []
    for path in sorted(CACHE.glob(f"sleeper_projections_{season}_w*.parquet")):
        frame = pl.read_parquet(path)
        frames.append(score_projection_frame(frame, scoring))
    return pl.concat(frames, how="diagonal_relaxed").filter(
        pl.col("position").is_in(VALID_POSITIONS)
    )


def prepare_players(history, weeks, sleeper_players, forced_ids=()):
    """Select players and build future projection matrix."""
    future = history.filter(pl.col("week").is_in(weeks)).with_columns(
        pl.col("proj_pts").fill_null(0)
    )
    ros = future.group_by("player_id").agg(
        pl.col("proj_pts").sum().alias("ros_points"),
        pl.col("name").drop_nulls().last(), pl.col("position").drop_nulls().last(),
        pl.col("team").drop_nulls().last(),
    ).filter(pl.col("team").is_not_null())
    top = set(ros.sort("ros_points", descending=True).head(450).get_column("player_id").to_list())
    extras = set(ros.filter(pl.col("position") == "QB").get_column("player_id").to_list())
    for position in ("K", "DEF"):
        extras.update(
            ros.filter(pl.col("position") == position).sort("ros_points", descending=True).head(32).get_column("player_id").to_list()
        )
    selected = ros.filter(
        pl.col("player_id").is_in(top | extras | {str(value) for value in forced_ids})
    ).sort("ros_points", descending=True)
    metadata = sleeper_players.select("player_id", "injury_status")
    players = selected.join(metadata, on="player_id", how="left").with_row_index("player_index")
    lookup = {
        (row["player_id"], row["week"]): float(row["proj_pts"] or 0)
        for row in history.iter_rows(named=True)
    }
    matrix = np.zeros((len(weeks), players.height), dtype=np.float32)
    for player_index, row in enumerate(players.iter_rows(named=True)):
        player_history = {
            week: points for (player, week), points in lookup.items() if player == row["player_id"]
        }
        for week_index, week in enumerate(weeks):
            value = player_history.get(week)
            if value is None:
                recent = [player_history[past] for past in sorted(
                    (past for past in player_history if past < week), reverse=True
                )[:3]]
                value = weighted_recent_projection(recent) if recent else 0.0
            matrix[week_index, player_index] = value
    return players, matrix


def schedule_inputs(schedules, weeks, players):
    """Build player bye masks and NFL game pairs."""
    bye = np.ones((len(weeks), players.height), dtype=bool)
    games = []
    teams = players.get_column("team").to_numpy()
    regular = schedules.filter((pl.col("season") == 2026) & (pl.col("game_type") == "REG"))
    for week_index, week in enumerate(weeks):
        rows = regular.filter(pl.col("week") == week)
        pairs = [
            (normalize_team(row["home_team"]), normalize_team(row["away_team"]))
            for row in rows.iter_rows(named=True)
        ]
        active = {team for pair in pairs for team in pair}
        bye[week_index] = np.array([team not in active for team in teams])
        games.append(pairs)
    return bye, games


def fixed_idp_schedule(games, team, weekly_points):
    """Return fixed IDP points by week, with zero during the player's bye."""
    normalized = normalize_team(team)
    return [
        float(weekly_points) if normalized in {club for game in week for club in game} else 0.0
        for week in games
    ]


def write_report(league, result, runtime, reproducible, teams, pending_overrides):
    """Write synthetic league odds."""
    lines = [
        "# League odds (synthetic opponents)", "",
        f"- n_final worlds + season runtime: {runtime:.3f} seconds",
        f"- Same-seed reproducibility check: {'passed' if reproducible else 'failed'}", "",
        "| Team | P(playoffs) | P(bye) | P(champion) | Expected wins | Expected points |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for index, team in enumerate(teams):
        lines.append(
            f"| {team} | {result['playoff_probability'][index]:.4f} | "
            f"{result['bye_probability'][index]:.4f} | {result['champion_probability'][index]:.4f} | "
            f"{result['expected_wins'][index]:.3f} | {result['expected_points_for'][index]:.2f} |"
        )
    lines.extend(["", "## Injury overrides needing Diego's input", ""])
    if pending_overrides:
        for row in pending_overrides:
            lines.append(
                f"- {row['name']}: weeks is TBD; override not applied. Note: {row.get('note', '')}."
            )
    else:
        lines.append("- None.")
    (ROOT / "reports/league_odds.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    config = load_config()
    schedules = pl.read_parquet(CACHE / "nflverse_schedules.parquet")
    completed = completed_weeks(schedules, 2026)
    first_week = max(completed) + 1
    weeks = list(range(first_week, config["league"]["playoff_weeks"][-1] + 1))
    partial_roster = pl.read_parquet(CACHE / "yahoo_partial_roster.parquet")
    real_roster_ids = partial_roster.filter(
        pl.col("sleeper_id").is_not_null() & ~pl.col("model_excluded")
    ).get_column("sleeper_id").cast(pl.String).to_list()
    history = load_projection_history(2026, config["scoring"])
    sleeper_players = pl.read_parquet(CACHE / "sleeper_players.parquet")
    players, projections = prepare_players(history, weeks, sleeper_players, real_roster_ids)
    market = load_market(CACHE)
    players = apply_model_fallback(
        players, market, sleeper_players,
        lineup=config["league"]["lineup"], overrides=load_injury_overrides(ROOT / "overrides.yaml"),
    )
    write_model_vs_market(players, market, ROOT / "reports/model_vs_market.md")
    bye, games = schedule_inputs(schedules, weeks, players)
    positions = players.get_column("position").to_numpy()
    teams = players.get_column("team").to_numpy()
    statuses = players.get_column("injury_status").to_numpy()
    statuses = np.array([status or "none" for status in statuses])
    player_names = players.get_column("name").fill_null(players.get_column("player_id")).to_numpy()
    overrides = load_injury_overrides(ROOT / "overrides.yaml")
    pending_overrides = [
        row for row in overrides if str(row.get("weeks", "")).upper() == "TBD"
    ]
    model = QuantileModel.load(ROOT / "models/quantiles_2026.npz")
    availability = json.loads((ROOT / "models/availability.json").read_text())
    qb_effect = json.loads((ROOT / "models/qb_effect.json").read_text())
    sigma = np.load(ROOT / "models/copula.npz")["Sigma"]

    draft_players = players.select(
        pl.col("player_id").alias("sleeper_id"), "name",
        pl.col("position").alias("pos"), "ros_points",
        pl.col("market_value_final").alias("market_value"),
    )
    league = partial_synthetic_league(
        draft_players, real_roster_ids, config["league"]["my_team"],
        teams=config["league"]["teams"], roster_size=15,
    )
    idp = partial_roster.filter(pl.col("model_excluded"))
    fixed_idp_points = float(idp.get_column("yahoo_proj_w7").fill_null(0).mean()) if idp.height else 0.0
    fixed_idp_team = idp.item(0, "nfl_team") if idp.height else None
    fixed_idp_week_points = fixed_idp_schedule(games, fixed_idp_team, fixed_idp_points) if idp.height else [0.0] * len(weeks)
    league["fixed_idp_points"] = fixed_idp_points
    league["fixed_idp_name"] = idp.item(0, "name") if idp.height else None
    league["fixed_idp_team"] = fixed_idp_team
    league["fixed_idp_week_points"] = fixed_idp_week_points
    league["free_agents_estimated"] = not (ROOT / "data/yahoo_paste/available.txt").exists()
    league["player_ids"] = players.get_column("player_id").to_list()
    (ROOT / "models/synthetic_league.json").write_text(json.dumps(league, indent=2), encoding="utf-8")

    small_a = generate_worlds(
        projections, bye, positions, teams, statuses, games, model, availability,
        qb_effect, sigma, 50, config["sim"]["seed"], player_names, overrides,
    )
    small_b = generate_worlds(
        projections, bye, positions, teams, statuses, games, model, availability,
        qb_effect, sigma, 50, config["sim"]["seed"], player_names, overrides,
    )
    reproducible = all(np.array_equal(left, right) for left, right in zip(small_a, small_b))

    started = time.perf_counter()
    points, available, proj_seen = generate_worlds(
        projections, bye, positions, teams, statuses, games, model, availability,
        qb_effect, sigma, config["sim"]["n_final"], config["sim"]["seed"],
        player_names, overrides,
    )
    team_scores = np.stack([
        roster_team_scores(points, proj_seen, available, positions, roster)
        for roster in league["rosters"]
    ], axis=2)
    team_scores[:, :, league["real_team_index"]] += np.asarray(fixed_idp_week_points)[:, None]
    result = simulate_team_scores(
        team_scores, weeks, config["league"]["regular_season_weeks"][1],
        config["league"]["playoff_teams"], config["league"]["playoff_reseeding"],
    )
    runtime = time.perf_counter() - started
    world_dir = Path(config["paths"]["worlds"]) / f"2026_w{first_week}"
    world_dir.mkdir(parents=True, exist_ok=True)
    write_world_manifest(ROOT / "models/world_manifest.json", world_dir, first_week)
    np.save(world_dir / "points.npy", points)
    np.save(world_dir / "available.npy", available)
    np.save(world_dir / "proj_seen.npy", proj_seen)
    np.save(world_dir / "week_numbers.npy", np.array(weeks))
    players.write_parquet(world_dir / "player_index.parquet")
    np.savez_compressed(
        world_dir / "season_results.npz", playoff=result["playoff"], bye=result["bye"],
        champion=result["champion"], champion_flags=result["champion_flags"],
        wins=result["wins"], points_for=result["points_for"],
        team_week_scores=result["team_week_scores"],
    )
    write_report(
        league, result, runtime, reproducible, league["teams"], pending_overrides,
    )
    print(f"first incomplete week: {first_week}")
    print(f"players: {players.height}; worlds: {config['sim']['n_final']}")
    print(f"runtime_seconds: {runtime:.3f}")
    print(f"reproducible: {reproducible}")
    print(f"sum_playoff_probability: {result['playoff_probability'].sum():.12f}")
    print(f"sum_champion_probability: {result['champion_probability'].sum():.12f}")


if __name__ == "__main__":
    main()
