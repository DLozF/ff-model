import numpy as np
import polars as pl


def implied_team_points(schedules: pl.DataFrame) -> pl.DataFrame:
    """Return pregame team implied points and week-relative deltas."""
    games = schedules.filter(
        (pl.col("game_type") == "REG")
        & pl.col("total_line").is_not_null()
        & pl.col("spread_line").is_not_null()
    )
    home = games.select(
        "season", "week", pl.col("home_team").alias("team"),
        (pl.col("total_line") / 2 + pl.col("spread_line") / 2).alias("implied_points"),
    )
    away = games.select(
        "season", "week", pl.col("away_team").alias("team"),
        (pl.col("total_line") / 2 - pl.col("spread_line") / 2).alias("implied_points"),
    )
    return pl.concat([home, away]).with_columns(
        (pl.col("implied_points") - pl.col("implied_points").mean().over("season", "week"))
        .alias("implied_delta")
    )


def add_vegas_feature(frame: pl.DataFrame, implied: pl.DataFrame) -> pl.DataFrame:
    """Join own implied points for offense and opponent implied points for DEF."""
    return (
        frame.with_row_index("_row")
        .with_columns(
            pl.when(pl.col("pos") == "DEF").then(pl.col("opp")).otherwise(pl.col("team"))
            .alias("_vegas_team")
        )
        .join(
            implied.rename({
                "team": "_vegas_team", "implied_points": "vegas_points",
                "implied_delta": "vegas_delta",
            }),
            on=["season", "week", "_vegas_team"], how="left",
        )
        .sort("_row")
        .drop("_row", "_vegas_team")
    )


def role_change_features(snaps: pl.DataFrame, mapping: pl.DataFrame) -> pl.DataFrame:
    """Compute prior-two minus prior-four snap share without same-week leakage."""
    joined = (
        snaps.select("season", "week", "pfr_player_id", "offense_pct")
        .join(mapping.select("pfr_id", "gsis_id"), left_on="pfr_player_id", right_on="pfr_id")
        .sort("season", "gsis_id", "week")
    )
    rows = []
    for group in joined.partition_by(["season", "gsis_id"], maintain_order=True):
        season = group.item(0, "season")
        gsis_id = group.item(0, "gsis_id")
        shares = dict(zip(group["week"].to_list(), group["offense_pct"].to_list()))
        for week in group["week"].to_list():
            recent = [shares[w] for w in range(week - 2, week) if w in shares]
            prior = [shares[w] for w in range(week - 6, week - 2) if w in shares]
            delta = None
            if len(recent) == 2 and len(prior) == 4:
                delta = round(float(np.mean(recent) - np.mean(prior)), 12)
            rows.append({"season": season, "week": week, "gsis_id": gsis_id, "role_delta": delta})
    return pl.DataFrame(rows, schema={
        "season": pl.Int64, "week": pl.Int64, "gsis_id": pl.String, "role_delta": pl.Float64,
    })


def fit_position_coefficients(
    frame: pl.DataFrame, feature: str, positions: tuple[str, ...]
) -> dict[str, float]:
    """Fit residual adjustments through zero by position."""
    coefficients = {}
    for position in positions:
        rows = frame.filter(
            (pl.col("pos") == position) & pl.col(feature).is_not_null() & pl.col("played")
        )
        x = rows.get_column(feature).to_numpy()
        y = (rows.get_column("act_pts") - rows.get_column("proj_pts")).to_numpy()
        denominator = float(x @ x)
        coefficients[position] = float(x @ y / denominator) if denominator else 0.0
    return coefficients


def adjust_projections(
    frame: pl.DataFrame, feature: str, coefficients: dict[str, float]
) -> pl.DataFrame:
    """Apply position-specific linear projection adjustments."""
    adjustment = pl.lit(0.0)
    for position, coefficient in coefficients.items():
        adjustment = pl.when(pl.col("pos") == position).then(
            pl.col(feature).fill_null(0.0) * coefficient
        ).otherwise(adjustment)
    return frame.with_columns((pl.col("proj_pts") + adjustment).clip(0).alias("proj_pts"))
