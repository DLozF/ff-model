import numpy as np


def regress_beta(kappa: np.ndarray, point_ratios: np.ndarray) -> float:
    """Regress skill-player point changes on backup-QB quality through zero."""
    x = np.asarray(kappa, dtype=float) - 1
    y = np.asarray(point_ratios, dtype=float) - 1
    denominator = float(x @ x)
    return float(x @ y / denominator) if denominator else 0.0
