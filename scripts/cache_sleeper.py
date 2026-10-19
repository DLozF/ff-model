from pathlib import Path

import polars as pl

from ffm.sleeper import cache_players, cache_state, cache_week


CACHE = Path("/opt/data/ff-model/data/cache")


def completed_2026_weeks() -> list[int]:
    """Return 2026 regular-season weeks whose games all have scores."""
    schedules = pl.read_parquet(CACHE / "nflverse_schedules.parquet").filter(
        (pl.col("season") == 2026) & (pl.col("game_type") == "REG")
    )
    complete = schedules.group_by("week").agg(
        (
            pl.col("home_score").is_not_null().all()
            & pl.col("away_score").is_not_null().all()
        ).alias("complete")
    )
    return sorted(complete.filter("complete").get_column("week").to_list())


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    state = cache_state(CACHE)
    cache_players(CACHE)
    for season in range(2021, 2026):
        for week in range(1, 19):
            cache_week(season, week, "projections", CACHE)
            cache_week(season, week, "stats", CACHE)
    completed = completed_2026_weeks()
    for week in completed:
        cache_week(2026, week, "projections", CACHE)
        cache_week(2026, week, "stats", CACHE)
    future = []
    for week in range(max(completed, default=0) + 1, 19):
        try:
            cache_week(2026, week, "projections", CACHE)
            future.append(week)
        except RuntimeError as error:
            print(f"projection unavailable: {error}")
    print(f"Sleeper state: {state}")
    print(f"Completed 2026 weeks: {completed}")
    print(f"Future 2026 projection weeks: {future}")


if __name__ == "__main__":
    main()
