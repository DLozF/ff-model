from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import norm

from ffm.backtest import matchup_metrics, paired_cluster_bootstrap
from ffm.copula import repair_correlation
from ffm.distributions import QuantileModel
from ffm.experiments import rolling_origin_split
from fit_copula import fit_sigma

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"
LINEUP = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1}


def slot_map(week):
    """Map played player row IDs to team slot indexes."""
    mapping = {}
    for group in week.partition_by("team", as_dict=False):
        for position, count, offset in (("QB", 1, 0), ("RB", 2, 1), ("WR", 3, 3), ("TE", 1, 6), ("K", 1, 7), ("DEF", 1, 8)):
            rows = group.filter(pl.col("pos") == position).sort("proj_pts", descending=True)
            for rank, row in enumerate(rows.head(count).iter_rows(named=True)):
                mapping[row["row_id"]] = offset + rank
    return mapping


def random_lineup(week, rng, excluded=None, stack=False):
    """Sample one legal threshold-qualified lineup."""
    excluded = set() if excluded is None else set(excluded)
    pools = {
        "QB": week.filter((pl.col("pos") == "QB") & (pl.col("proj_pts") >= 12)),
        "RB": week.filter((pl.col("pos") == "RB") & (pl.col("proj_pts") >= 6)),
        "WR": week.filter((pl.col("pos") == "WR") & (pl.col("proj_pts") >= 6)),
        "TE": week.filter((pl.col("pos") == "TE") & (pl.col("proj_pts") >= 4)),
        "K": week.filter(pl.col("pos") == "K"),
        "DEF": week.filter(pl.col("pos") == "DEF"),
    }
    pools = {
        position: [row for row in pool.iter_rows(named=True) if row["row_id"] not in excluded]
        for position, pool in pools.items()
    }
    chosen = []
    if stack:
        wr1 = {
            group.row(0, named=True)["team"]: group.sort("proj_pts", descending=True).row(0, named=True)
            for group in week.filter((pl.col("pos") == "WR") & (pl.col("proj_pts") >= 6)).partition_by("team", as_dict=False)
        }
        qbs = [row for row in pools["QB"] if row["team"] in wr1 and wr1[row["team"]]["row_id"] not in excluded]
        if not qbs:
            raise ValueError("no stack available")
        qb = qbs[rng.integers(len(qbs))]
        chosen.extend([qb, wr1[qb["team"]]])
    for position, count in LINEUP.items():
        already = sum(row["pos"] == position for row in chosen)
        candidates = [row for row in pools[position] if row["row_id"] not in {item["row_id"] for item in chosen}]
        need = count - already
        if len(candidates) < need:
            raise ValueError(f"not enough {position}")
        if need:
            selected = rng.choice(len(candidates), size=need, replace=False)
            chosen.extend(candidates[int(index)] for index in np.atleast_1d(selected))
    flex_pool = [
        row for position in ("RB", "WR", "TE") for row in pools[position]
        if row["row_id"] not in {item["row_id"] for item in chosen}
    ]
    if not flex_pool:
        raise ValueError("not enough FLEX")
    chosen.append(flex_pool[rng.integers(len(flex_pool))])
    return chosen


def pair_correlation(players, slots, sigma):
    """Build the selected-player latent correlation matrix."""
    size = len(players)
    correlation = np.eye(size)
    for left in range(size):
        for right in range(left + 1, size):
            a, b = players[left], players[right]
            slot_a, slot_b = slots.get(a["row_id"]), slots.get(b["row_id"])
            value = 0.0
            if slot_a is not None and slot_b is not None:
                if a["team"] == b["team"]:
                    value = sigma[slot_a, slot_b]
                elif a["opp"] == b["team"]:
                    value = sigma[slot_a, 9 + slot_b]
            correlation[left, right] = correlation[right, left] = value
    return repair_correlation(correlation, shrink=0.0)


def predict_pair(model, sigma, slots, lineup_a, lineup_b, rng, worlds=2000):
    """Predict matchup win probabilities with copula and independence."""
    players = lineup_a + lineup_b
    half = worlds // 2
    base_half = rng.standard_normal((half, len(players)))
    base = np.concatenate([base_half, -base_half], axis=0)
    correlated = base @ np.linalg.cholesky(pair_correlation(players, slots, sigma)).T
    probabilities = []
    for latent in (correlated, base):
        uniforms = norm.cdf(latent)
        simulated = np.empty_like(uniforms)
        positions = np.array([row["pos"] for row in players])
        projections = np.array([row["proj_pts"] for row in players])
        for position in np.unique(positions):
            indices = np.flatnonzero(positions == position)
            simulated[:, indices] = model.ppf(
                position, np.broadcast_to(projections[indices], (worlds, indices.size)),
                uniforms[:, indices],
            )
        probabilities.append(float(np.mean(simulated[:, :9].sum(axis=1) > simulated[:, 9:].sum(axis=1))))
    return probabilities


def run_season(frame, season, seed):
    """Run one leakage-safe season matchup backtest."""
    train, test = rolling_origin_split(frame.filter(pl.col("played")), season)
    model = QuantileModel.fit(train, k=500, smooth=9)
    schedules = pl.read_parquet(CACHE / "nflverse_schedules.parquet")
    sigma, _ = fit_sigma(train, model, schedules)
    selection_rng = np.random.default_rng(seed)
    simulation_rng = np.random.default_rng(seed + 10_000)
    rows = []
    for week_number in sorted(test.get_column("week").unique().to_list()):
        week = test.filter(pl.col("week") == week_number).with_row_index("row_id")
        slots = slot_map(week)
        for stacked, count in ((False, 300), (True, 100)):
            made = 0
            attempts = 0
            while made < count and attempts < count * 20:
                attempts += 1
                try:
                    lineup_a = random_lineup(week, selection_rng, stack=stacked)
                    lineup_b = random_lineup(
                        week, selection_rng, excluded=[row["row_id"] for row in lineup_a]
                    )
                except ValueError:
                    continue
                copula, independent = predict_pair(
                    model, sigma, slots, lineup_a, lineup_b, simulation_rng
                )
                actual_a = sum(row["act_pts"] for row in lineup_a)
                actual_b = sum(row["act_pts"] for row in lineup_b)
                rows.append({
                    "season": season, "week": week_number, "stacked": stacked,
                    "outcome": float(actual_a > actual_b), "copula": copula,
                    "independent": independent,
                })
                made += 1
            if made != count:
                raise RuntimeError(f"only generated {made}/{count} pairs for {season} week {week_number}")
    return rows


def main():
    frame = pl.read_parquet(CACHE / "player_weeks.parquet")
    rows = run_season(frame, 2024, 2026) + run_season(frame, 2025, 2027)
    pl.from_dicts(rows).write_parquet(CACHE / "matchup_predictions.parquet")
    results = {}
    for label, selected in (
        ("overall", rows), ("stacked", [row for row in rows if row["stacked"]]),
    ):
        outcome = np.array([row["outcome"] for row in selected])
        results[label] = {
            model: matchup_metrics(np.array([row[model] for row in selected]), outcome)
            for model in ("copula", "independent")
        }
        differences = (
            (np.array([row["copula"] for row in selected]) - outcome) ** 2
            - (np.array([row["independent"] for row in selected]) - outcome) ** 2
        )
        clusters = np.array([f"{row['season']}_w{row['week']}" for row in selected])
        results[label]["brier_difference"] = paired_cluster_bootstrap(
            differences, clusters, seed=2026 + len(results)
        )
    lines = ["# Matchup calibration", ""]
    for label in ("overall", "stacked"):
        difference = results[label]["brier_difference"]
        lines.extend([
            f"## {label.title()}", "",
            f"- Copula minus independent Brier: {difference['mean']:+.8f} "
            f"(paired week-bootstrap 95% interval [{difference['low']:+.8f}, {difference['high']:+.8f}])",
            "",
            "| Model | Pairs | Brier | Log loss | Worst bin error |", "|---|---:|---:|---:|---:|",
        ])
        for model in ("copula", "independent"):
            metrics = results[label][model]
            worst = max(row["error"] for row in metrics["calibration"] if row["n"])
            lines.append(f"| {model} | {sum(row['n'] for row in metrics['calibration'])} | {metrics['brier']:.6f} | {metrics['log_loss']:.6f} | {worst:.6f} |")
        lines.extend([
            "", "### Calibration bins", "",
            "| Bin | Copula pairs | Copula predicted | Copula actual | Copula error | Independent pairs | Independent predicted | Independent actual | Independent error |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        copula_bins = results[label]["copula"]["calibration"]
        independent_bins = results[label]["independent"]["calibration"]
        for copula, independent in zip(copula_bins, independent_bins):
            if copula["n"] or independent["n"]:
                lines.append(
                    f"| {copula['bin']} | {copula['n']} | {copula['predicted']:.4f} | "
                    f"{copula['actual']:.4f} | {copula['error']:.4f} | {independent['n']} | "
                    f"{independent['predicted']:.4f} | {independent['actual']:.4f} | "
                    f"{independent['error']:.4f} |"
                )
        lines.append("")
    (ROOT / "reports/matchup_calibration.md").write_text("\n".join(lines), encoding="utf-8")
    for label in results:
        copula = results[label]["copula"]
        independent = results[label]["independent"]
        worst = max(row["error"] for row in copula["calibration"] if row["n"])
        print(label, "copula_brier", copula["brier"], "independent_brier", independent["brier"], "worst_bin", worst)


if __name__ == "__main__":
    main()
