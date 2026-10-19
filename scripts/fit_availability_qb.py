import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import polars as pl

from ffm.availability import DEFAULTS, estimate_markov, status_play_probabilities
from ffm.ids import NFL_TEAMS, normalize_team
from ffm.qb import regress_beta

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"
POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")


def bye_weeks(schedules):
    """Build season-week-team bye keys."""
    result = set()
    regular = schedules.filter(
        pl.col("game_type") == "REG", pl.col("season").is_between(2021, 2025)
    )
    for season in range(2021, 2026):
        for week in range(1, 19):
            games = regular.filter((pl.col("season") == season) & (pl.col("week") == week))
            active = {
                normalize_team(team)
                for team in games.select("home_team", "away_team").to_numpy().ravel()
            }
            result.update((season, week, team) for team in NFL_TEAMS - active)
    return result


def injury_status_rows(player_weeks, injuries):
    """Join final weekly injury status to player outcomes."""
    final = (
        injuries.filter(pl.col("season").is_between(2021, 2025))
        .sort("date_modified")
        .group_by("season", "week", "gsis_id")
        .agg(pl.col("report_status").last())
    )
    return player_weeks.filter(
        pl.col("season").is_between(2021, 2025), pl.col("pos").is_in(POSITIONS)
    ).join(final, on=["season", "week", "gsis_id"], how="left")


def apply_sanity(markov, status):
    """Replace failed availability estimates with declared defaults."""
    assumptions = []
    for position, values in markov.items():
        if values["h"] is None or not 0.01 < values["h"] < 0.2:
            assumptions.append(f"{position} h={values['h']} replaced with {DEFAULTS['h'][position]}")
            values["h_raw"] = values["h"]
            values["h"] = DEFAULTS["h"][position]
        if values["r"] is None or not 0.1 < values["r"] < 0.9:
            assumptions.append(f"{position} r={values['r']} replaced with {DEFAULTS['r'][position]}")
            values["r_raw"] = values["r"]
            values["r"] = DEFAULTS["r"][position]
    for label in ("Out", "Questionable"):
        estimate = status.get(label, {}).get("probability")
        valid = estimate is not None and (
            estimate < 0.05 if label == "Out" else 0.5 < estimate < 0.95
        )
        if not valid:
            assumptions.append(
                f"P(play|{label})={estimate} replaced with {DEFAULTS['status'][label]}"
            )
            status.setdefault(label, {})["raw_probability"] = estimate
            status[label]["probability"] = DEFAULTS["status"][label]
    for label, default in DEFAULTS["status"].items():
        status.setdefault(label, {"probability": default, "n": 0})
    return assumptions


def qb_effects(frame):
    """Estimate backup QB quality and skill-position sensitivity."""
    training = frame.filter(pl.col("season").is_between(2021, 2025))
    qbs = training.filter((pl.col("pos") == "QB") & pl.col("team").is_not_null())
    week_modes = {}
    ratios = []
    history = defaultdict(dict)
    for group in qbs.partition_by(["season", "team", "week"], as_dict=False):
        rows = sorted(group.iter_rows(named=True), key=lambda row: row["proj_pts"], reverse=True)
        qb1 = rows[0]
        key = (qb1["season"], qb1["team"], qb1["week"])
        if qb1["played"]:
            week_modes[key] = 1.0
            history[(qb1["season"], qb1["sleeper_id"])][qb1["week"]] = qb1["proj_pts"]
            continue
        backups = [row for row in rows[1:] if row["played"]]
        prior = history[(qb1["season"], qb1["sleeper_id"])]
        prior_weeks = [week for week in prior if week < qb1["week"]]
        if not backups or not prior_weeks:
            continue
        baseline = prior[max(prior_weeks)]
        if baseline <= 0:
            continue
        ratio = backups[0]["act_pts"] / baseline
        ratios.append(ratio)
        week_modes[key] = ratio
    kappa = float(np.mean(ratios)) if len(ratios) >= 30 else 0.75
    result = {"kappa": kappa, "kappa_sample_size": len(ratios), "beta": {}}
    defaults = {"WR": 0.6, "TE": 0.6, "RB": 0.3}
    for position, default in defaults.items():
        kappas = []
        point_ratios = []
        skill = training.filter((pl.col("pos") == position) & pl.col("played"))
        for group in skill.partition_by(["season", "team", "sleeper_id"], as_dict=False):
            starter_points = []
            backup_points = []
            backup_kappas = []
            for row in group.iter_rows(named=True):
                mode = week_modes.get((row["season"], row["team"], row["week"]))
                if mode is None:
                    continue
                if mode == 1.0:
                    starter_points.append(row["act_pts"])
                else:
                    backup_points.append(row["act_pts"])
                    backup_kappas.append(mode)
            if starter_points and backup_points and np.mean(starter_points) > 0:
                kappas.append(float(np.mean(backup_kappas)))
                point_ratios.append(float(np.mean(backup_points) / np.mean(starter_points)))
        beta = regress_beta(np.array(kappas), np.array(point_ratios)) if len(kappas) >= 30 else default
        result["beta"][position] = {"value": beta, "sample_size": len(kappas), "default_used": len(kappas) < 30}
    return result


def main():
    frame = pl.read_parquet(CACHE / "player_weeks.parquet")
    schedules = pl.read_parquet(CACHE / "nflverse_schedules.parquet")
    injuries = pl.read_parquet(CACHE / "nflverse_injuries.parquet")
    training = frame.filter(pl.col("season").is_between(2021, 2025))
    markov = estimate_markov(training, bye_weeks(schedules), POSITIONS)
    status = status_play_probabilities(injury_status_rows(training, injuries))
    assumptions = apply_sanity(markov, status)
    availability = {
        "markov": markov,
        "status_play_probability": status,
        "r_ir": {"value": DEFAULTS["r_ir"], "sample_size": 0, "default_used": True},
        "assumptions": assumptions + ["Historical IR transitions unavailable; r_IR defaulted to 0.25."],
    }
    effects = qb_effects(training)
    (ROOT / "models/availability.json").write_text(json.dumps(availability, indent=2), encoding="utf-8")
    (ROOT / "models/qb_effect.json").write_text(json.dumps(effects, indent=2), encoding="utf-8")
    print(json.dumps(availability, indent=2))
    print(json.dumps(effects, indent=2))


if __name__ == "__main__":
    main()
