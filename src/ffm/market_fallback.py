"""Model fallback values for players the FantasyCalc market does not cover.

FantasyCalc publishes values only for its own ~196-player list and never
lists kickers or team defenses.  Unmatched players therefore received V=0,
which made trades involving them look free (AJ Barner for Christian
McCaffrey read ACCEPT).  This module estimates a market value for every
unmatched player from the model's own rest-of-season points above
replacement, mapped monotonically onto the matched players' FantasyCalc V.
"""
import numpy as np
import polars as pl
from sklearn.isotonic import IsotonicRegression

VALUE_SOURCES = ("fantasycalc", "name_match", "model_fallback", "out")

OUT_STATUS = {"Out", "IR", "PUP", "NA", "Sus", "COV"}

MARKET_COLUMNS = (
    "market_name", "market_position", "market_team", "market_value",
    "trend_30_day", "market_overall_rank", "market_position_rank",
)


def fit_replacement_index(
    players: pl.DataFrame,
    lineup: dict[str, int] | None = None,
    flex_eligible: tuple[str, ...] = ("RB", "WR", "TE"),
) -> dict[str, int]:
    """Return the replacement player's rank per position (0-based, most points first)."""
    slots = dict(lineup or {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1})
    flex = int(slots.pop("FLEX", 0) or 0)
    per_flex = flex / len(flex_eligible) if flex_eligible else 0.0
    counts = players.group_by("position").agg(pl.len().alias("n"))
    size = {row["position"]: row["n"] for row in counts.iter_rows(named=True)}
    index = {}
    for pos in set(slots) | set(flex_eligible):
        need = slots.get(pos, 0) + (per_flex if pos in flex_eligible else 0.0)
        if need > 0:
            index[pos] = int(np.ceil(min(need, size.get(pos, 0)))) - 1
    return index


def replacement_points(players: pl.DataFrame, index: dict[str, int]) -> dict[str, float]:
    """Return rest-of-season points at each position's replacement rank."""
    points = {}
    for pos, rank in index.items():
        block = players.filter(pl.col("position") == pos).sort("ros_points", descending=True)
        if 0 <= rank < block.height:
            points[pos] = float(block.get_column("ros_points")[rank])
    return points


def _fit_map(ros_points: np.ndarray, values: np.ndarray) -> IsotonicRegression:
    model = IsotonicRegression(out_of_bounds="clip", y_min=0.0)
    model.fit(ros_points, values)
    return model


def _normalize_market(market: pl.DataFrame) -> pl.DataFrame:
    """Coerce any market frame into sleeper_id/name/position/team/value."""
    columns = {column.lower(): column for column in market.columns}
    def pick(*names: str) -> str | None:
        for name in names:
            if name in columns:
                return columns[name]
        return None

    sid = pick("sleeper_id", "player_sleeperid")
    value = pick("market_value", "redraftvalue")
    frame = market.select(
        pl.col(sid).cast(pl.String).alias("sleeper_id"),
        (pl.col(pick("market_name", "player_name")).alias("market_name")
         if pick("market_name", "player_name") else pl.lit(None).alias("market_name")),
        (pl.col(pick("market_position", "player_position")).alias("market_position")
         if pick("market_position", "player_position") else pl.lit(None).alias("market_position")),
        (pl.col(pick("market_team", "player_maybeteam")).alias("market_team")
         if pick("market_team", "player_maybeteam") else pl.lit(None).alias("market_team")),
        pl.col(value).cast(pl.Float64).alias("market_value"),
    )
    return frame.filter(pl.col("sleeper_id").is_not_null())


def apply_model_fallback(
    players: pl.DataFrame,
    market: pl.DataFrame,
    sleeper_players: pl.DataFrame,
    lineup: dict[str, int] | None = None,
    overrides: list[dict] | None = None,
) -> pl.DataFrame:
    """Attach ``value_source``, ``model_value`` and final ``market_value_final``.

    ``players`` must carry ``player_index``, ``player_id``, ``name``,
    ``position``, ``team`` and ``ros_points``.  Second-pass matching keys on
    normalized name + position + team, so K and DEF never steal an ID.
    Out-for-season players (Sleeper Out/IR, or an ``overrides.yaml`` entry
    with ``status: out``) get V=0 with source ``out``; every other market
    miss gets the isotonic model fallback, capped per position.
    """
    from ffm.yahoo_paste import normalize_player_name

    players = players.drop(
        [column for column in MARKET_COLUMNS if column in players.columns]
        + [column for column in ("value_source", "model_value", "market_value_final") if column in players.columns]
    )
    market = _normalize_market(market)
    joined = players.with_columns(pl.col("player_id").cast(pl.String)).join(
        market.select("sleeper_id", "market_value").unique(subset="sleeper_id"),
        left_on="player_id", right_on="sleeper_id", how="left",
    )
    status = sleeper_players.select(
        pl.col("player_id").cast(pl.String).alias("_pid"),
        pl.col("injury_status").alias("_fallback_injury_status"),
        pl.col("status").alias("_fallback_status"),
    ).unique(subset="_pid")
    joined = joined.join(status, left_on="player_id", right_on="_pid", how="left")
    if "injury_status" in joined.columns:
        joined = joined.with_columns(
            pl.coalesce(["injury_status", "_fallback_injury_status"]).alias("injury_status")
        )
    else:
        joined = joined.with_columns(
            pl.col("_fallback_injury_status").alias("injury_status")
        )
    joined = joined.with_columns(pl.col("_fallback_status").alias("status"))
    joined = joined.with_columns(pl.col("market_value").is_not_null().alias("market_matched"))

    # Second pass: normalized name + position + team for still-unmatched players.
    player_key = pl.struct(
        pl.col("name").map_elements(normalize_player_name, return_dtype=pl.String).alias("n"),
        pl.col("position").alias("p"),
        pl.col("team").alias("t"),
    )
    market_key_frame = (
        market.filter(pl.col("market_name").is_not_null())
        .with_columns(
            pl.struct(
                pl.col("market_name").map_elements(
                    normalize_player_name, return_dtype=pl.String
                ).alias("n"),
                pl.col("market_position").alias("p"),
                pl.col("market_team").alias("t"),
            ).alias("_key")
        )
        .unique(subset="_key")
        .select("_key", pl.col("market_value").alias("_name_match_value"))
    )
    joined = joined.with_columns(player_key.alias("_key")).join(
        market_key_frame, on="_key", how="left"
    )
    joined = joined.with_columns(
        pl.coalesce(["market_value", "_name_match_value"]).alias("market_value")
    )
    joined = joined.with_columns(
        pl.when(pl.col("market_matched"))
        .then(pl.lit("fantasycalc"))
        .when(pl.col("_name_match_value").is_not_null())
        .then(pl.lit("name_match"))
        .otherwise(None)
        .alias("value_source")
    ).drop("_name_match_value")

    override_names = {
        str(row.get("name", "")).strip().lower()
        for row in (overrides or [])
        if str(row.get("status", "")).lower() in {"out", "out_for_season", "ir"}
    }
    is_out = (
        pl.col("injury_status").is_in(sorted(OUT_STATUS))
        | (pl.col("status") == "Injured Reserve")
        | pl.col("name").str.to_lowercase().is_in(sorted(override_names))
    )
    joined = joined.with_columns(
        pl.when(is_out & pl.col("value_source").is_null())
        .then(pl.lit("out"))
        .otherwise(pl.col("value_source"))
        .alias("value_source")
    )

    replacement_index = fit_replacement_index(joined, lineup)
    rep_points = replacement_points(joined, replacement_index)
    joined = joined.with_columns(
        pl.struct("position", "ros_points")
        .map_elements(
            lambda row: float(row["ros_points"]) - rep_points.get(row["position"], 0.0),
            return_dtype=pl.Float64,
        )
        .alias("model_value")
    )

    flex_matched = joined.filter(
        pl.col("market_matched") & ~pl.col("position").is_in(["K", "DEF"])
    )
    lowest_flex_v = float(flex_matched.get_column("market_value").min()) if flex_matched.height else 0.0
    cap = min(lowest_flex_v, 2.0)  # K/DEF fallbacks never reach the flex floor

    blocks = []
    for position in sorted(joined.get_column("position").unique().to_list()):
        block = joined.filter(pl.col("position") == position)
        known = block.filter(pl.col("market_matched"))
        out_rows = block.filter(pl.col("value_source") == "out")
        fallback = block.filter(
            pl.col("value_source").is_null() | (pl.col("value_source") == "name_match")
        )
        if fallback.height:
            if known.height >= 5:
                model = _fit_map(
                    known.get_column("model_value").to_numpy(),
                    known.get_column("market_value").to_numpy(),
                )
                predicted = model.predict(fallback.get_column("model_value").to_numpy())
                if position in {"K", "DEF"}:
                    predicted = np.minimum(predicted, cap)
                else:
                    predicted = np.minimum(predicted, max(lowest_flex_v, 0.0))
                predicted = np.maximum(predicted, 0.0)
            else:
                predicted = fallback.get_column("market_value").to_numpy()
                predicted = np.where(
                    np.isnan(predicted), fallback.get_column("model_value").to_numpy(), predicted
                )
                predicted = np.maximum(predicted, 0.0)
            fallback = fallback.with_columns(
                pl.Series("fallback_value", predicted, dtype=pl.Float64)
            )
        blocks.extend([
            known.with_columns(
                pl.col("market_value").cast(pl.Float64).alias("fallback_value")
            ),
            out_rows.with_columns(pl.lit(0.0, dtype=pl.Float64).alias("fallback_value")),
            fallback,
        ])
    result = pl.concat(
        [block for block in blocks if block.height], how="vertical"
    ).sort("player_index")
    result = result.with_columns(
        pl.when(pl.col("value_source").is_null())
        .then(pl.lit("model_fallback"))
        .otherwise(pl.col("value_source"))
        .alias("value_source")
    )
    return result.with_columns(
        pl.col("fallback_value").fill_null(0.0).alias("market_value_final")
    ).drop([
        "market_matched", "_key", "model_value", "fallback_value", "market_value",
        "status", "_fallback_injury_status", "_fallback_status",
    ], strict=False)
