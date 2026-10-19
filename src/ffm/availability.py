from collections import defaultdict

import polars as pl

DEFAULTS = {
    "h": {"QB": 0.04, "RB": 0.08, "WR": 0.07, "TE": 0.07, "K": 0.03, "DEF": 0.02},
    "r": {"QB": 0.60, "RB": 0.55, "WR": 0.55, "TE": 0.55, "K": 0.65, "DEF": 0.80},
    "r_ir": 0.25,
    "status": {"Out": 0.02, "Doubtful": 0.25, "Questionable": 0.75, "none": 0.98},
}


def estimate_markov(
    frame: pl.DataFrame,
    bye_weeks: set[tuple[int, int, str]],
    positions: list[str] | tuple[str, ...],
) -> dict[str, dict]:
    """Estimate weekly play/miss transition rates by position."""
    counts = {position: defaultdict(int) for position in positions}
    groups = frame.partition_by(["season", "sleeper_id"], as_dict=False)
    for group in groups:
        if group.get_column("proj_pts").mean() < 5:
            continue
        rows = group.sort("week").iter_rows(named=True)
        previous = None
        for row in rows:
            if previous is not None and row["week"] == previous["week"] + 1:
                current_bye = (row["season"], row["week"], row["team"]) in bye_weeks
                previous_bye = (
                    previous["season"], previous["week"], previous["team"]
                ) in bye_weeks
                if not current_bye and not previous_bye and previous["pos"] in counts:
                    position = previous["pos"]
                    if previous["played"]:
                        counts[position]["h_n"] += 1
                        counts[position]["h_events"] += int(not row["played"])
                    else:
                        counts[position]["r_n"] += 1
                        counts[position]["r_events"] += int(row["played"])
            previous = row
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
