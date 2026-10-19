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
