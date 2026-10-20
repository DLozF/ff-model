import polars as pl

from ffm.ids import normalize_team
from ffm.scoring import NFLVERSE_TO_SCORING, fantasy_points, nflverse_stat_line

PLAYER_POSITIONS = ("QB", "RB", "WR", "TE", "K")


def merge_actual_sources(sleeper: pl.DataFrame, nflverse: pl.DataFrame) -> pl.DataFrame:
    """Merge actual sources with explicit nflverse supplements taking precedence."""
    return pl.concat([sleeper, nflverse], how="diagonal_relaxed").unique(
        subset=["season", "week", "player_id"], keep="last", maintain_order=True
    )


def replace_season(existing: pl.DataFrame, fresh: pl.DataFrame, season: int) -> pl.DataFrame:
    """Replace one season in a cached multi-season nflverse table."""
    return pl.concat(
        [existing.filter(pl.col("season") != season), fresh], how="diagonal_relaxed"
    )


def nflverse_actual_rows(
    stats: pl.DataFrame, ids: pl.DataFrame, scoring: dict
) -> pl.DataFrame:
    """Convert nflverse weekly player stats into canonical scored actual rows."""
    identity = ids.select(
        pl.col("gsis_id").cast(pl.String).alias("player_id"),
        pl.col("sleeper_id").cast(pl.String),
    ).drop_nulls().unique("player_id")
    joined = stats.filter(pl.col("position").is_in(PLAYER_POSITIONS)).join(
        identity, on="player_id", how="inner"
    )
    records = []
    for row in joined.iter_rows(named=True):
        mapped = nflverse_stat_line(row)
        records.append({
            "season": int(row["season"]),
            "week": int(row["week"]),
            "player_id": row["sleeper_id"],
            **mapped,
            "pts_ppr": fantasy_points(mapped, row["position"], scoring),
            "gp": 1.0,
        })
    schema = {
        "season": pl.Int64,
        "week": pl.Int64,
        "player_id": pl.String,
        **{key: pl.Float64 for key in NFLVERSE_TO_SCORING},
        "pts_ppr": pl.Float64,
        "gp": pl.Float64,
    }
    return pl.from_dicts(records, schema=schema).sort("season", "week", "player_id")


def projection_team_gaps(
    projections: pl.DataFrame, actuals: pl.DataFrame, schedules: pl.DataFrame
) -> pl.DataFrame:
    """Find completed season/week/team groups with projections but no actual row."""
    completed = (
        schedules.filter(pl.col("game_type") == "REG")
        .group_by("season", "week")
        .agg(
            (
                pl.col("home_score").is_not_null().all()
                & pl.col("away_score").is_not_null().all()
            ).alias("complete")
        )
        .filter(pl.col("complete"))
        .select(
            pl.col("season").cast(pl.Int64),
            pl.col("week").cast(pl.Int64),
        )
    )
    projected = (
        projections.select("season", "week", "player_id", "team")
        .drop_nulls(["team"])
        .with_columns(
            pl.col("season").cast(pl.Int64),
            pl.col("week").cast(pl.Int64),
            pl.col("player_id").cast(pl.String),
            pl.col("team").map_elements(normalize_team, return_dtype=pl.String),
        )
        .join(completed, on=["season", "week"], how="inner")
    )
    actual_keys = actuals.select("season", "week", "player_id").with_columns(
        pl.col("season").cast(pl.Int64),
        pl.col("week").cast(pl.Int64),
        pl.col("player_id").cast(pl.String),
    ).unique()
    counts = (
        projected.join(actual_keys.with_columns(pl.lit(1).alias("has_actual")),
                       on=["season", "week", "player_id"], how="left")
        .group_by("season", "week", "team")
        .agg(
            pl.len().alias("projection_rows"),
            pl.col("has_actual").fill_null(0).sum().alias("actual_rows"),
        )
    )
    gaps = counts.filter(pl.col("actual_rows") == 0)
    regular = schedules.filter(pl.col("game_type") == "REG")
    home = regular.select(
        pl.col("season").cast(pl.Int64),
        pl.col("week").cast(pl.Int64),
        pl.col("home_team").map_elements(normalize_team, return_dtype=pl.String).alias("team"),
    )
    away = regular.select(
        pl.col("season").cast(pl.Int64),
        pl.col("week").cast(pl.Int64),
        pl.col("away_team").map_elements(normalize_team, return_dtype=pl.String).alias("team"),
    )
    active = pl.concat([home, away]).unique().with_columns(
        pl.lit(True).alias("scheduled_game")
    )
    return (
        gaps.join(active, on=["season", "week", "team"], how="left")
        .with_columns(pl.col("scheduled_game").fill_null(False))
        .sort("season", "week", "team")
    )
