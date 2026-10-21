"""Weekly empirical interval coverage for daily monitoring."""

import numpy as np
import polars as pl

from ffm.distributions import POSITIONS, QuantileModel


def weekly_position_coverage(
    player_weeks: pl.DataFrame,
    model: QuantileModel,
    season: int,
    nominal: float = 0.80,
) -> pl.DataFrame:
    """Return played-player coverage by completed week and position."""
    rows = player_weeks.filter(
        (pl.col("season") == season)
        & pl.col("played")
        & pl.col("pos").is_in(POSITIONS)
        & pl.col("proj_pts").is_not_null()
        & pl.col("act_pts").is_not_null()
    )
    low_level = (1.0 - nominal) / 2.0
    high_level = 1.0 - low_level
    low_index = int(np.argmin(np.abs(model.levels - low_level)))
    high_index = int(np.argmin(np.abs(model.levels - high_level)))
    results = []
    for week in sorted(rows.get_column("week").unique().to_list()):
        for position in POSITIONS:
            block = rows.filter((pl.col("week") == week) & (pl.col("pos") == position))
            if block.is_empty() or position not in model.tables:
                continue
            quantiles = model.quantile_matrix(
                position, block.get_column("proj_pts").to_numpy()
            )
            actual = block.get_column("act_pts").to_numpy()
            covered = (actual >= quantiles[:, low_index]) & (actual <= quantiles[:, high_index])
            results.append({
                "season": int(season),
                "week": int(week),
                "position": position,
                "players": int(block.height),
                "nominal": float(nominal),
                "coverage": float(covered.mean()),
            })
    return pl.from_dicts(results) if results else pl.DataFrame({
        "season": [], "week": [], "position": [], "players": [],
        "nominal": [], "coverage": [],
    })


def latest_coverage_lines(coverage: pl.DataFrame) -> list[str]:
    """Format one daily-report line per position for the latest completed week."""
    if coverage.is_empty():
        return ["- Weekly 80% coverage: no completed player-weeks available."]
    latest_week = int(coverage.get_column("week").max())
    latest = coverage.filter(pl.col("week") == latest_week)
    by_position = {
        row["position"]: row for row in latest.iter_rows(named=True)
    }
    lines = []
    nominal = int(round(float(latest.get_column("nominal")[0]) * 100))
    for position in POSITIONS:
        row = by_position.get(position)
        if row is None:
            lines.append(
                f"- Week {latest_week} {position} {nominal}% coverage: no played players."
            )
        else:
            lines.append(
                f"- Week {latest_week} {position} {nominal}% coverage: "
                f"{row['coverage']:.1%} (n={row['players']})."
            )
    return lines
