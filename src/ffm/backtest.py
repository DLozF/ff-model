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
