import numpy as np

from ffm.qb import regress_beta


def test_regress_beta_fits_through_origin():
    kappa = np.array([0.5, 0.75, 0.9])
    ratios = 1 + 0.6 * (kappa - 1)

    beta = regress_beta(kappa, ratios)

    assert abs(beta - 0.6) < 1e-12
