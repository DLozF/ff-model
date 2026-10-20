from pathlib import Path

import nflreadpy as nfl

from ffm.pbp_bonus import select_bonus_pbp


ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"
SEASONS = list(range(2021, 2027))


def cache(name, loader):
    """Download one nflverse dataset and cache it as Parquet."""
    path = CACHE / f"nflverse_{name}.parquet"
    if path.exists():
        print(f"{name}: cached {path}")
        return
    frame = loader()
    print(f"{name} columns: {frame.columns}")
    print(f"{name} rows: {frame.height}")
    print(frame.head(3).to_dicts())
    frame.write_parquet(path)


def cache_pbp_bonus(season):
    """Cache the compact play-by-play fields needed for custom scoring."""
    path = CACHE / f"nflverse_pbp_bonus_{season}.parquet"
    if path.exists():
        print(f"pbp_bonus_{season}: cached {path}")
        return
    frame = select_bonus_pbp(nfl.load_pbp([season]))
    print(f"pbp_bonus_{season} columns: {frame.columns}")
    print(f"pbp_bonus_{season} rows: {frame.height}")
    print(frame.head(3).to_dicts())
    frame.write_parquet(path)


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    cache("schedules", lambda: nfl.load_schedules(SEASONS))
    cache("player_stats", lambda: nfl.load_player_stats(SEASONS, summary_level="week"))
    cache("injuries", lambda: nfl.load_injuries(SEASONS))
    cache("snap_counts", lambda: nfl.load_snap_counts(SEASONS))
    cache("ff_playerids", nfl.load_ff_playerids)
    cache("ff_opportunity", lambda: nfl.load_ff_opportunity(SEASONS))
    for season in SEASONS:
        cache_pbp_bonus(season)


if __name__ == "__main__":
    main()
