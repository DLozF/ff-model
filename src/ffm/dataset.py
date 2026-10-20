from collections.abc import Mapping

import polars as pl

from ffm.ids import normalize_team
from ffm.scoring import fantasy_points

OUTPUT_COLUMNS = [
    "season", "week", "sleeper_id", "gsis_id", "name", "pos", "team", "opp",
    "proj_pts", "act_pts", "played",
]


def _snap_keys(snaps: pl.DataFrame, ids: pl.DataFrame) -> set[tuple[int, int, str]]:
    if snaps.is_empty() or ids.is_empty() or "pfr_id" not in ids.columns:
        return set()
    mapping = ids.select(
        pl.col("pfr_id").cast(pl.String), pl.col("sleeper_id").cast(pl.String)
    ).drop_nulls()
    played = snaps.join(mapping, left_on="pfr_player_id", right_on="pfr_id", how="inner").filter(
        pl.sum_horizontal("offense_snaps", "defense_snaps", "st_snaps") > 0
    )
    return set(played.select("season", "week", "sleeper_id").iter_rows())


def build_player_weeks(
    projections: pl.DataFrame,
    stats: pl.DataFrame,
    players: pl.DataFrame,
    ids: pl.DataFrame,
    snaps: pl.DataFrame,
    scoring: Mapping,
) -> pl.DataFrame:
    """Build the canonical player-week modeling table."""
    projection_rows = {
        (int(row["season"]), int(row["week"]), str(row["player_id"])): row
        for row in projections.iter_rows(named=True)
    }
    stat_rows = {
        (int(row["season"]), int(row["week"]), str(row["player_id"])): row
        for row in stats.iter_rows(named=True)
    }
    player_rows = {
        str(row["player_id"]): row for row in players.iter_rows(named=True)
    }
    id_rows = {}
    if not ids.is_empty() and "sleeper_id" in ids.columns:
        id_rows = {
            str(row["sleeper_id"]): row
            for row in ids.iter_rows(named=True)
            if row.get("sleeper_id") is not None
        }
    snap_keys = _snap_keys(snaps, ids)
    records = []
    for key in projection_rows.keys() | stat_rows.keys():
        season, week, sleeper_id = key
        projection = projection_rows.get(key, {})
        actual = stat_rows.get(key)
        player = player_rows.get(sleeper_id, {})
        identity = id_rows.get(sleeper_id, {})
        position = projection.get("position") or player.get("position") or identity.get("position")
        if position not in {"QB", "RB", "WR", "TE", "K", "DEF"}:
            continue
        proj_pts = fantasy_points(projection, position, scoring, include_bonuses=False)
        act_pts = fantasy_points(actual or {}, position, scoring)
        if proj_pts < 0.5 and act_pts == 0:
            continue
        team = projection.get("team") or player.get("team") or identity.get("team")
        name = projection.get("name") or player.get("full_name") or identity.get("name")
        if position == "DEF":
            name = name or normalize_team(sleeper_id)
            team = team or sleeper_id
        records.append({
            "season": season,
            "week": week,
            "sleeper_id": sleeper_id,
            "gsis_id": player.get("gsis_id") or identity.get("gsis_id"),
            "name": name,
            "pos": position,
            "team": normalize_team(team),
            "opp": normalize_team(projection.get("opponent")),
            "proj_pts": proj_pts,
            "act_pts": act_pts,
            "played": actual is not None and (
                float(actual.get("gp") or 0) > 0 or act_pts != 0 or key in snap_keys
            ),
        })
    return pl.from_dicts(records, schema={
        "season": pl.Int64, "week": pl.Int64, "sleeper_id": pl.String,
        "gsis_id": pl.String, "name": pl.String, "pos": pl.String,
        "team": pl.String, "opp": pl.String, "proj_pts": pl.Float64,
        "act_pts": pl.Float64, "played": pl.Boolean,
    }).select(OUTPUT_COLUMNS).sort("season", "week", "sleeper_id")
