import numpy as np
from scipy.stats import norm, t


def copula_uniforms(
    base: np.ndarray,
    factor: np.ndarray,
    df: int | None = None,
    chi_square: np.ndarray | None = None,
) -> np.ndarray:
    """Transform common normal draws into Gaussian or t-copula uniforms."""
    latent = np.asarray(base) @ np.asarray(factor).T
    if df is None:
        return norm.cdf(latent)
    if chi_square is None:
        raise ValueError("chi_square draws are required for a t-copula")
    scaled = latent / np.sqrt(np.asarray(chi_square)[:, None] / df)
    return t.cdf(scaled, df=df)


def pairwise_correlation(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute pairwise-complete correlations and observation counts."""
    values = np.asarray(values, dtype=float)
    dimensions = values.shape[1]
    correlation = np.eye(dimensions)
    counts = np.zeros((dimensions, dimensions), dtype=np.int32)
    for left in range(dimensions):
        for right in range(left, dimensions):
            complete = np.isfinite(values[:, left]) & np.isfinite(values[:, right])
            count = int(complete.sum())
            counts[left, right] = counts[right, left] = count
            if left == right:
                value = 1.0
            elif count < 2:
                value = 0.0
            else:
                x = values[complete, left]
                y = values[complete, right]
                value = float(np.corrcoef(x, y)[0, 1]) if np.std(x) and np.std(y) else 0.0
                if not np.isfinite(value):
                    value = 0.0
            correlation[left, right] = correlation[right, left] = value
    return correlation, counts


def symmetrize_team_blocks(correlation: np.ndarray, slots: int = 9) -> np.ndarray:
    """Impose exchangeability of own and opponent team blocks."""
    result = np.asarray(correlation, dtype=float).copy()
    same_team = (result[:slots, :slots] + result[slots:, slots:]) / 2
    cross_team = (result[:slots, slots:] + result[:slots, slots:].T) / 2
    result[:slots, :slots] = same_team
    result[slots:, slots:] = same_team
    result[:slots, slots:] = cross_team
    result[slots:, :slots] = cross_team.T
    return result


def repair_correlation(correlation: np.ndarray, shrink: float = 0.1) -> np.ndarray:
    """Repair a correlation matrix to positive definite and shrink to identity."""
    symmetric = (np.asarray(correlation) + np.asarray(correlation).T) / 2
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    repaired = (eigenvectors * np.maximum(eigenvalues, 1e-4)) @ eigenvectors.T
    scale = np.sqrt(np.diag(repaired))
    repaired = repaired / np.outer(scale, scale)
    repaired = (1 - shrink) * repaired + shrink * np.eye(repaired.shape[0])
    return (repaired + repaired.T) / 2
