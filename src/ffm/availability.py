from collections import defaultdict

import polars as pl

DEFAULTS = {
    "h": {"QB": 0.04, "RB": 0.08, "WR": 0.07, "TE": 0.07, "K": 0.03, "DEF": 0.0},
    "r": {"QB": 0.60, "RB": 0.55, "WR": 0.55, "TE": 0.55, "K": 0.65, "DEF": 0.80},
    "r_ir": 0.25,
    "status": {"Out": 0.02, "Doubtful": 0.25, "Questionable": 0.75, "none": 0.98},
}
FANTASY_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")


def estimate_markov(
    frame: pl.DataFrame,
    bye_weeks: set[tuple[int, int, str]],
    positions: list[str] | tuple[str, ...],
) -> dict[str, dict]:
    """Estimate play/miss transitions, filling absent rows inside active windows."""
    counts = {position: defaultdict(int) for position in positions}
    groups = frame.partition_by(["season", "sleeper_id"], as_dict=False)
    for group in groups:
        if group.get_column("proj_pts").mean() < 5:
            continue
        records = group.sort("week").iter_rows(named=True)
        rows = list(records)
        played_weeks = [int(row["week"]) for row in rows if row["played"]]
        if len(played_weeks) < 2:
            continue
        first, last = min(played_weeks), max(played_weeks)
        by_week = {int(row["week"]): row for row in rows}
        default = rows[0]
        for week in range(first, last):
            previous = by_week.get(week, default)
            current = by_week.get(week + 1, previous)
            position = previous["pos"]
            if position not in counts:
                continue
            previous_bye = (previous["season"], week, previous["team"]) in bye_weeks
            current_bye = (current["season"], week + 1, current["team"]) in bye_weeks
            if previous_bye or current_bye:
                continue
            previous_played = bool(by_week.get(week, {}).get("played", False))
            current_played = bool(by_week.get(week + 1, {}).get("played", False))
            if previous_played:
                counts[position]["h_n"] += 1
                counts[position]["h_events"] += int(not current_played)
            else:
                counts[position]["r_n"] += 1
                counts[position]["r_events"] += int(current_played)
    result = {}
    for position in positions:
        count = counts[position]
        result[position] = {
            "h": count["h_events"] / count["h_n"] if count["h_n"] else None,
            "r": count["r_events"] / count["r_n"] if count["r_n"] else None,
            "h_n": count["h_n"],
            "r_n": count["r_n"],
        }
    return result


def status_play_probabilities(rows: pl.DataFrame) -> dict[str, dict]:
    """Estimate same-week play probability by injury report status."""
    counts = defaultdict(lambda: [0, 0])
    for row in rows.iter_rows(named=True):
        status = row.get("report_status") or "none"
        counts[status][0] += int(row["played"])
        counts[status][1] += 1
    return {
        status: {"probability": played / total, "n": total}
        for status, (played, total) in counts.items()
    }


def injury_status_outcomes(
    player_weeks: pl.DataFrame,
    injuries: pl.DataFrame,
    stats: pl.DataFrame,
    snaps: pl.DataFrame,
    ids: pl.DataFrame,
) -> pl.DataFrame:
    """Match every final injury designation to actual same-week participation."""
    final = (
        injuries.sort("date_modified")
        .group_by("season", "week", "gsis_id")
        .agg(pl.col("position").last(), pl.col("report_status").last())
        .filter(pl.col("position").is_in(FANTASY_POSITIONS))
        .with_columns(
            pl.col("season").cast(pl.Int64),
            pl.col("week").cast(pl.Int64),
            pl.col("gsis_id").cast(pl.String),
        )
    )
    played_from_stats = stats.select(
        "season", "week", pl.col("player_id").alias("gsis_id")
    ).drop_nulls().with_columns(
        pl.col("season").cast(pl.Int64),
        pl.col("week").cast(pl.Int64),
        pl.col("gsis_id").cast(pl.String),
    ).unique()
    played_from_model = player_weeks.filter(pl.col("played")).select(
        "season", "week", "gsis_id"
    ).drop_nulls().with_columns(
        pl.col("season").cast(pl.Int64),
        pl.col("week").cast(pl.Int64),
        pl.col("gsis_id").cast(pl.String),
    ).unique()
    played_sources = [played_from_stats, played_from_model]
    if not snaps.is_empty() and not ids.is_empty():
        mapping = ids.select("pfr_id", "gsis_id").drop_nulls().unique()
        snap_keys = (
            snaps.filter(
                pl.sum_horizontal("offense_snaps", "defense_snaps", "st_snaps") > 0
            )
            .join(mapping, left_on="pfr_player_id", right_on="pfr_id", how="inner")
            .select("season", "week", "gsis_id")
            .with_columns(
                pl.col("season").cast(pl.Int64),
                pl.col("week").cast(pl.Int64),
                pl.col("gsis_id").cast(pl.String),
            )
            .unique()
        )
        played_sources.append(snap_keys)
    played = pl.concat(played_sources).unique().with_columns(pl.lit(True).alias("played"))
    listed = (
        final.join(played, on=["season", "week", "gsis_id"], how="left")
        .with_columns(pl.col("played").fill_null(False))
        .select("report_status", "played")
    )
    unlisted = (
        player_weeks.join(
            final.select("season", "week", "gsis_id"),
            on=["season", "week", "gsis_id"],
            how="anti",
        )
        .select(pl.lit(None, dtype=pl.String).alias("report_status"), "played")
    )
    return pl.concat([listed, unlisted])
