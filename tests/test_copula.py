import numpy as np

from ffm.copula import pairwise_correlation, repair_correlation


def test_pairwise_correlation_counts_complete_pairs():
    values = np.array([[1.0, 2.0, np.nan], [2.0, 4.0, 3.0], [3.0, 6.0, 5.0]])
    corr, counts = pairwise_correlation(values)

    assert counts[0, 1] == 3
    assert counts[0, 2] == 2
    assert abs(corr[0, 1] - 1) < 1e-12


def test_repair_correlation_is_positive_definite():
    broken = np.array([[1.0, 1.2, -0.5], [1.2, 1.0, 0.8], [-0.5, 0.8, 1.0]])
    repaired = repair_correlation(broken)

    assert np.allclose(repaired, repaired.T)
    assert np.allclose(np.diag(repaired), 1)
    assert np.linalg.eigvalsh(repaired).min() > 0
