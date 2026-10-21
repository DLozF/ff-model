import numpy as np


def pinball_crps(actual: np.ndarray, quantiles: np.ndarray, levels: np.ndarray) -> np.ndarray:
    """Approximate CRPS from a quantile grid."""
    error = np.asarray(actual)[:, None] - np.asarray(quantiles)
    loss = np.maximum(levels * error, (levels - 1) * error)
    return 2 * loss.mean(axis=1)


def coverage(actual: np.ndarray, lower: np.ndarray, upper: np.ndarray) -> float:
    """Return inclusive empirical interval coverage."""
    actual = np.asarray(actual)
    return float(np.mean((actual >= lower) & (actual <= upper)))


def pit_values(actual: np.ndarray, quantiles: np.ndarray) -> np.ndarray:
    """Approximate PIT values from modeled quantiles."""
    return (np.sum(quantiles < np.asarray(actual)[:, None], axis=1) + 0.5) / quantiles.shape[1]


def pit_histogram(actual: np.ndarray, quantiles: np.ndarray) -> np.ndarray:
    """Return a ten-bin PIT histogram."""
    values = np.clip(pit_values(actual, quantiles), 0, 1)
    return np.histogram(values, bins=np.linspace(0, 1, 11))[0]


def matchup_metrics(probability: np.ndarray, outcome: np.ndarray) -> dict:
    """Compute binary forecast scores and a ten-bin calibration table."""
    probability = np.asarray(probability, dtype=float)
    outcome = np.asarray(outcome, dtype=float)
    clipped = np.clip(probability, 1e-12, 1 - 1e-12)
    order = np.argsort(probability)
    groups = np.array_split(order, 10)
    calibration = []
    for index, selected in enumerate(groups):
        if selected.size:
            predicted = float(probability[selected].mean())
            actual = float(outcome[selected].mean())
            calibration.append({
                "bin": index, "n": int(selected.size), "predicted": predicted,
                "actual": actual, "error": abs(predicted - actual),
            })
        else:
            calibration.append({"bin": index, "n": 0, "predicted": None, "actual": None, "error": None})
    return {
        "brier": float(np.mean((probability - outcome) ** 2)),
        "log_loss": float(np.mean(-(outcome * np.log(clipped) + (1 - outcome) * np.log(1 - clipped)))),
        "calibration": calibration,
    }


def wilson_interval(successes: int, probability: float, confidence: float = 0.95) -> tuple[float, float]:
    """Return the Wilson score interval for one binomial proportion."""
    from scipy.stats import norm

    successes = max(int(successes), 0)
    z = float(norm.ppf(0.5 + confidence / 2))
    denominator = 1 + z**2 / successes
    center = (probability + z**2 / (2 * successes)) / denominator
    spread = z * np.sqrt(probability * (1 - probability) / successes + z**2 / (4 * successes**2)) / denominator
    return float(np.clip(center - spread, 0, 1)), float(np.clip(center + spread, 0, 1))


def ece_bootstrap(
    probability: np.ndarray, outcome: np.ndarray, seed: int, samples: int = 1000, bins: int = 10
) -> dict[str, float]:
    """Bootstrap the expected calibration error with a 95% interval."""
    probability = np.asarray(probability, dtype=float)
    outcome = np.asarray(outcome, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    indices = np.clip(np.digitize(probability, edges[1:-1]), 0, bins - 1)

    def one(indices: np.ndarray) -> float:
        total = 0.0
        for group in range(bins):
            selected = indices == group
            if selected.sum():
                total += selected.sum() / indices.size * abs(probability[selected].mean() - outcome[selected].mean())
        return total

    observed = one(indices)
    rng = np.random.default_rng(seed)
    estimates = [
        one(rng.integers(0, indices.size, size=indices.size))
        for _ in range(samples)
        if indices.size
    ] or [observed]
    center = float(np.mean(estimates))
    spread = float(np.std(estimates, ddof=1)) if len(estimates) > 1 else 0.0
    low, high = np.quantile(estimates, [0.025, 0.975])
    if spread == 0:
        low = high = center
    return {"mean": float(observed), "low": float(min(low, observed)), "high": float(max(high, observed))}


def paired_cluster_bootstrap(
    differences: np.ndarray,
    clusters: np.ndarray,
    seed: int,
    samples: int = 5000,
) -> dict[str, float]:
    """Bootstrap a paired mean difference by resampling whole clusters."""
    differences = np.asarray(differences, dtype=float)
    clusters = np.asarray(clusters)
    unique = np.unique(clusters)
    sums = np.array([differences[clusters == cluster].sum() for cluster in unique])
    counts = np.array([(clusters == cluster).sum() for cluster in unique])
    rng = np.random.default_rng(seed)
    selected = rng.integers(0, unique.size, size=(samples, unique.size))
    estimates = sums[selected].sum(axis=1) / counts[selected].sum(axis=1)
    low, high = np.quantile(estimates, [0.025, 0.975])
    return {
        "mean": float(differences.mean()),
        "low": float(low),
        "high": float(high),
    }
