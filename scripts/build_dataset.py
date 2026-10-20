import re
from pathlib import Path

import polars as pl

from ffm.actuals import merge_actual_sources
from ffm.config import load_config
from ffm.dataset import build_player_weeks
from ffm.pbp_bonus import aggregate_bonus_stats, merge_bonus_stats
from ffm.scoring import fantasy_points

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"
SCORING_KEYS = {
    "pass_yd", "pass_td", "pass_int", "pass_2pt", "rush_yd", "rush_td",
    "rush_2pt", "rec", "rec_yd", "rec_td", "rec_2pt", "fum_lost",
    "ret_td", "kr_td", "pr_td", "xpm", "fgm_0_19", "fgm_20_29",
    "fgm_30_39", "fgm_40_49", "fgm_50p", "fgm_50_59", "fgm_60p",
    "sack", "int", "fum_rec", "def_td", "safe", "blk_kick", "pts_allow",
    "pass_cmp_40p", "pass_td_40p", "rush_40p", "rush_td_40p", "rec_40p",
    "rec_td_40p", "off_fum_ret_td", "fourth_down_stop", "def_4_and_stop",
    "xp_return", "def_kr_pr_td", "def_kr_td", "def_pr_td",
    "pts_ppr", "gp",
}


def _week_from_path(path: Path) -> tuple[int, int]:
    match = re.search(r"_(\d{4})_w(\d{2})", path.name)
    if not match:
        raise ValueError(f"cannot parse week from {path}")
    return int(match.group(1)), int(match.group(2))


def load_projections() -> pl.DataFrame:
    """Load cached weekly Sleeper projections."""
    frames = []
    for path in sorted(CACHE.glob("sleeper_projections_*.parquet")):
        frame = pl.read_parquet(path)
        columns = [
            "season", "week", "player_id", "name", "position", "team",
            "opponent", *sorted(SCORING_KEYS & set(frame.columns)),
        ]
        frames.append(frame.select(list(dict.fromkeys(columns))))
    return pl.concat(frames, how="diagonal_relaxed")


def load_stats() -> pl.DataFrame:
    """Load cached weekly Sleeper actual stats."""
    source_frames = []
    for pattern in ("sleeper_stats_*.parquet", "nflverse_actuals_*.parquet"):
        frames = []
        for path in sorted(CACHE.glob(pattern)):
            season, week = _week_from_path(path)
            frame = pl.read_parquet(path)
            columns = ["player_id", *sorted(SCORING_KEYS & set(frame.columns))]
            frames.append(frame.select(columns).with_columns(
                pl.lit(season).alias("season"), pl.lit(week).alias("week")
            ))
        source_frames.append(
            pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()
        )
    if source_frames[1].is_empty():
        return source_frames[0]
    return merge_actual_sources(*source_frames)


def load_bonus_stats(ids: pl.DataFrame) -> pl.DataFrame:
    """Load or build cached play-by-play bonus counts."""
    path = CACHE / "nflverse_pbp_bonuses.parquet"
    if path.exists():
        return pl.read_parquet(path)
    frames = [pl.read_parquet(source) for source in sorted(CACHE.glob("nflverse_pbp_bonus_*.parquet"))]
    bonus = aggregate_bonus_stats(pl.concat(frames, how="diagonal_relaxed"), ids)
    bonus.write_parquet(path)
    return bonus


def validation_rate(
    projections: pl.DataFrame, stats: pl.DataFrame, players: pl.DataFrame, scoring: dict
) -> tuple[int, int, float, list[dict]]:
    """Compare recomputed offense scores with Sleeper PPR points."""
    positions = {
        (row["season"], row["week"], row["player_id"]): row["position"]
        for row in projections.select("season", "week", "player_id", "position").iter_rows(named=True)
    }
    player_pos = {
        row["player_id"]: row["position"]
        for row in players.select("player_id", "position").iter_rows(named=True)
    }
    comparisons = []
    for row in stats.iter_rows(named=True):
        pos = positions.get((row["season"], row["week"], row["player_id"])) or player_pos.get(row["player_id"])
        if pos not in {"QB", "RB", "WR", "TE"} or row.get("pts_ppr") is None:
            continue
        recomputed = fantasy_points(row, pos, scoring)
        difference = abs(recomputed - float(row["pts_ppr"]))
        comparisons.append({
            "season": row["season"], "week": row["week"], "player_id": row["player_id"],
            "pos": pos, "sleeper": float(row["pts_ppr"]), "recomputed": recomputed,
            "difference": difference,
        })
    matched = sum(row["difference"] <= 0.5 for row in comparisons)
    largest = sorted(comparisons, key=lambda row: row["difference"], reverse=True)[:20]
    return matched, len(comparisons), matched / len(comparisons), largest


def main():
    config = load_config()
    projections = load_projections()
    stats = load_stats()
    players = pl.read_parquet(CACHE / "sleeper_players.parquet")
    ids = pl.read_parquet(CACHE / "nflverse_ff_playerids.parquet")
    stats = merge_bonus_stats(stats, load_bonus_stats(ids))
    snaps = pl.read_parquet(CACHE / "nflverse_snap_counts.parquet")
    player_weeks = build_player_weeks(
        projections, stats, players, ids, snaps, config["scoring"]
    )
    output = CACHE / "player_weeks.parquet"
    player_weeks.write_parquet(output)
    matched, total, rate, largest = validation_rate(
        projections, stats, players, config["scoring"]
    )
    training_rows = player_weeks.filter(pl.col("season").is_between(2021, 2025)).height
    print(f"player_weeks rows: {player_weeks.height}")
    print(f"training rows: {training_rows}")
    print(f"score match within 0.5: {matched}/{total} = {rate:.6f}")
    if rate < 0.95:
        print(f"largest mismatches: {largest}")


if __name__ == "__main__":
    main()
