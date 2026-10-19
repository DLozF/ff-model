from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import norm

from ffm.backtest import pit_values
from ffm.copula import pairwise_correlation, repair_correlation, symmetrize_team_blocks
from ffm.distributions import QuantileModel

ROOT = Path("/opt/data/ff-model")
CACHE = ROOT / "data/cache"
SLOTS = ("QB1", "RB1", "RB2", "WR1", "WR2", "WR3", "TE1", "K", "DEF")


def opponent_map(schedules):
    """Map each regular-season team-week to its opponent."""
    mapping = {}
    games = schedules.filter(pl.col("game_type") == "REG")
    for row in games.iter_rows(named=True):
        mapping[(row["season"], row["week"], row["home_team"])] = row["away_team"]
        mapping[(row["season"], row["week"], row["away_team"])] = row["home_team"]
    return mapping


def latent_rows(frame, model):
    """Attach latent normal scores to played player weeks."""
    parts = []
    for position in model.tables:
        rows = frame.filter((pl.col("pos") == position) & pl.col("played"))
        if rows.is_empty():
            continue
        quantiles = model.quantile_matrix(position, rows.get_column("proj_pts").to_numpy())
        u = pit_values(rows.get_column("act_pts").to_numpy(), quantiles)
        parts.append(rows.with_columns(pl.Series("z", norm.ppf(np.clip(u, 0.001, 0.999)))))
    return pl.concat(parts, how="diagonal_relaxed")


def team_vectors(frame):
    """Rank played players into nine team-week copula slots."""
    vectors = {}
    stack_rows = []
    for group in frame.partition_by(["season", "week", "team"], as_dict=False):
        first = group.row(0, named=True)
        key = (first["season"], first["week"], first["team"])
        values = np.full(9, np.nan)
        selected = {}
        slot_plan = (("QB", 1, 0), ("RB", 2, 1), ("WR", 3, 3), ("TE", 1, 6), ("K", 1, 7), ("DEF", 1, 8))
        for position, count, offset in slot_plan:
            rows = group.filter(pl.col("pos") == position).sort("proj_pts", descending=True)
            for rank, row in enumerate(rows.head(count).iter_rows(named=True)):
                values[offset + rank] = row["z"]
                selected[SLOTS[offset + rank]] = row
        vectors[key] = values
        if all(slot in selected for slot in ("QB1", "WR1", "TE1")):
            stack_rows.append({
                "season": key[0], "week": key[1], "team": key[2],
                "qb_proj": selected["QB1"]["proj_pts"], "wr_proj": selected["WR1"]["proj_pts"],
                "te_proj": selected["TE1"]["proj_pts"],
                "actual": selected["QB1"]["act_pts"] + selected["WR1"]["act_pts"] + selected["TE1"]["act_pts"],
            })
    return vectors, stack_rows


def game_matrix(vectors, opponents):
    """Create both orientations of every team-game vector."""
    rows = []
    for key, own in vectors.items():
        opponent = opponents.get(key)
        other = vectors.get((key[0], key[1], opponent))
        if other is not None:
            rows.append(np.concatenate([own, other]))
    return np.array(rows)


def fit_sigma(frame, model, schedules):
    """Fit and repair the 18-dimensional game copula."""
    vectors, _ = team_vectors(latent_rows(frame, model))
    matrix = game_matrix(vectors, opponent_map(schedules))
    correlation, counts = pairwise_correlation(matrix)
    sigma = repair_correlation(symmetrize_team_blocks(correlation))
    return sigma, counts


def stack_variance_ratio(model, sigma, stacks, seed, worlds=1000):
    """Compare held-out stack error variance with simulated variance."""
    rng = np.random.default_rng(seed)
    submatrix = sigma[np.ix_([0, 3, 6], [0, 3, 6])]
    factor = np.linalg.cholesky(submatrix)
    errors = []
    simulated_variances = []
    for row in stacks:
        z = rng.standard_normal((worlds, 3)) @ factor.T
        u = norm.cdf(z)
        qb = model.ppf("QB", np.full(worlds, row["qb_proj"]), u[:, 0])
        wr = model.ppf("WR", np.full(worlds, row["wr_proj"]), u[:, 1])
        te = model.ppf("TE", np.full(worlds, row["te_proj"]), u[:, 2])
        total = qb + wr + te
        errors.append(row["actual"] - total.mean())
        simulated_variances.append(total.var(ddof=1))
    return float(np.var(errors, ddof=1) / np.mean(simulated_variances))


def main():
    frame = pl.read_parquet(CACHE / "player_weeks.parquet")
    schedules = pl.read_parquet(CACHE / "nflverse_schedules.parquet")
    training = frame.filter(pl.col("season").is_between(2021, 2025) & pl.col("played"))
    final_model = QuantileModel.load(ROOT / "models/quantiles_2026.npz")
    sigma, counts = fit_sigma(training, final_model, schedules)
    np.savez_compressed(
        ROOT / "models/copula.npz", Sigma=sigma.astype(np.float32),
        pair_counts=counts, slots=np.array(SLOTS),
    )

    pre2025 = training.filter(pl.col("season") <= 2024)
    heldout = training.filter(pl.col("season") == 2025)
    heldout_model = QuantileModel.fit(pre2025, k=500, smooth=9)
    heldout_sigma, _ = fit_sigma(pre2025, heldout_model, schedules)
    _, stacks = team_vectors(latent_rows(heldout, heldout_model))
    copula_ratio = stack_variance_ratio(heldout_model, heldout_sigma, stacks, 2026)
    independent_ratio = stack_variance_ratio(heldout_model, np.eye(18), stacks, 2026)
    minimum_eigenvalue = float(np.linalg.eigvalsh(sigma).min())
    qb_wr = float(sigma[0, 3])
    report = "\n".join([
        "# Copula validation", "",
        f"- Minimum eigenvalue: {minimum_eigenvalue:.6f}",
        f"- Same-team QB1-WR1 correlation: {qb_wr:.6f}",
        f"- Held-out 2025 stack variance ratio, copula: {copula_ratio:.6f}",
        f"- Held-out 2025 stack variance ratio, independent: {independent_ratio:.6f}",
        f"- Held-out stacks: {len(stacks)}", "",
    ])
    (ROOT / "reports/copula.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
