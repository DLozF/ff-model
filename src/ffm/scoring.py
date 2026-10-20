from collections.abc import Mapping

import polars as pl


NFLVERSE_TO_SCORING = {
    "pass_yd": "passing_yards",
    "pass_td": "passing_tds",
    "pass_int": "passing_interceptions",
    "pass_2pt": "passing_2pt_conversions",
    "rush_yd": "rushing_yards",
    "rush_td": "rushing_tds",
    "rush_2pt": "rushing_2pt_conversions",
    "rec": "receptions",
    "rec_yd": "receiving_yards",
    "rec_td": "receiving_tds",
    "rec_2pt": "receiving_2pt_conversions",
    "fum_lost": "fumbles_lost_total",
    "ret_td": "special_teams_tds",
    "pass_cmp_40p": "passing_40",
    "rush_40p": "rushing_40",
    "rec_40p": "receiving_40",
    "xpm": "pat_made",
    "fgm_0_19": "fg_made_0_19",
    "fgm_20_29": "fg_made_20_29",
    "fgm_30_39": "fg_made_30_39",
    "fgm_40_49": "fg_made_40_49",
    "fgm_50_59": "fg_made_50_59",
    "fgm_60p": "fg_made_60_",
}


def _value(stats: Mapping, key: str) -> float:
    value = stats.get(key, 0)
    return float(value) if value is not None else 0.0


def nflverse_stat_line(stats: Mapping) -> dict[str, float]:
    """Map nflverse weekly player-stat fields to the configured scoring keys."""
    return {
        scoring_key: _value(stats, nflverse_key)
        for scoring_key, nflverse_key in NFLVERSE_TO_SCORING.items()
    }


def _defense_tier(points: float, tiers: Mapping[str, float]) -> float:
    if points == 0:
        return float(tiers["0"])
    if points <= 6:
        return float(tiers["1-6"])
    if points <= 13:
        return float(tiers["7-13"])
    if points <= 20:
        return float(tiers["14-20"])
    if points <= 27:
        return float(tiers["21-27"])
    if points <= 34:
        return float(tiers["28-34"])
    return float(tiers["35+"])


def _milestone_bonus(stats: Mapping, scoring: Mapping, key: str) -> float:
    milestones = scoring.get(f"{key}_milestones", [])
    reached = [float(row["points"]) for row in milestones if _value(stats, key) >= row["threshold"]]
    if not reached:
        return 0.0
    return sum(reached) if scoring.get("milestone_mode") == "stacked" else max(reached)


def fantasy_points(
    stats: Mapping, position: str, scoring: Mapping, include_bonuses: bool = True
) -> float:
    """Score a Sleeper stat line with the configured league rules."""
    if position == "DEF":
        total = (
            _value(stats, "sack") * scoring["def_sack"]
            + _value(stats, "int") * scoring["def_int"]
            + _value(stats, "fum_rec") * scoring["def_fum_rec"]
            + _value(stats, "def_td") * scoring["def_td"]
            + _value(stats, "safe") * scoring["def_safety"]
            + _value(stats, "blk_kick") * scoring["def_blk_kick"]
            + (_value(stats, "fourth_down_stop") + _value(stats, "def_4_and_stop"))
            * scoring.get("def_fourth_down_stop", 0)
            + _value(stats, "xp_return") * scoring.get("def_xp_return", 0)
            + (_value(stats, "def_kr_pr_td") + _value(stats, "def_kr_td") + _value(stats, "def_pr_td"))
            * scoring.get("def_kr_pr_td", 0)
        )
        return total + _defense_tier(_value(stats, "pts_allow"), scoring["def_pts_allowed"])

    if position == "K":
        fgm_50p = _value(stats, "fgm_50p")
        if "fgm_50p" not in stats:
            fgm_50p = _value(stats, "fgm_50_59") + _value(stats, "fgm_60p")
        return (
            _value(stats, "xpm") * scoring["xpm"]
            + _value(stats, "fgm_0_19") * scoring["fgm_0_19"]
            + _value(stats, "fgm_20_29") * scoring["fgm_20_29"]
            + _value(stats, "fgm_30_39") * scoring["fgm_30_39"]
            + _value(stats, "fgm_40_49") * scoring["fgm_40_49"]
            + fgm_50p * scoring["fgm_50p"]
        )

    total = sum(
        _value(stats, key) * scoring[key]
        for key in (
            "pass_yd", "pass_td", "pass_int", "pass_2pt", "rush_yd",
            "rush_td", "rush_2pt", "rec", "rec_yd", "rec_td", "rec_2pt",
            "fum_lost",
        )
    ) + (
        _value(stats, "ret_td") + _value(stats, "kr_td") + _value(stats, "pr_td")
    ) * scoring["ret_td"] + (
        _value(stats, "off_fum_ret_td") + _value(stats, "fum_rec_ez_tds")
    ) * scoring.get("off_fum_ret_td", 0)
    if include_bonuses:
        total += sum(
            _value(stats, stat_key) * scoring.get(score_key, 0)
            for stat_key, score_key in (
                ("pass_cmp_40p", "pass_cmp_40p"), ("pass_td_40p", "pass_td_40p"),
                ("rush_40p", "rush_40p"), ("rush_td_40p", "rush_td_40p"),
                ("rec_40p", "rec_40p"), ("rec_td_40p", "rec_td_40p"),
            )
        )
        total += sum(_milestone_bonus(stats, scoring, key) for key in ("pass_yd", "rush_yd", "rec_yd"))
    return total


def score_projection_frame(frame: pl.DataFrame, scoring: Mapping) -> pl.DataFrame:
    """Rescore Sleeper projected stat lines without unprojectable play bonuses."""
    return frame.with_columns(
        pl.struct(frame.columns).map_elements(
            lambda row: fantasy_points(
                row, row.get("position"), scoring, include_bonuses=False
            ),
            return_dtype=pl.Float64,
        ).alias("proj_pts")
    )
