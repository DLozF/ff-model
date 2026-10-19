import numpy as np

from ffm.worlds import weighted_recent_projection


def test_weighted_recent_projection_uses_321_weights():
    assert weighted_recent_projection([6.0, 12.0, 18.0]) == 10.0
    assert weighted_recent_projection([12.0, 18.0]) == 14.0
    assert weighted_recent_projection([18.0]) == 18.0
