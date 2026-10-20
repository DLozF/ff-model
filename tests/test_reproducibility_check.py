import numpy as np

from scripts.reproducibility_check import run_once


def test_reproducibility_probe_is_identical_for_same_seed():
    first_digest, first = run_once(2026)
    second_digest, second = run_once(2026)

    assert first_digest == second_digest
    for key in first:
        np.testing.assert_array_equal(first[key], second[key])


def test_reproducibility_probe_changes_with_seed():
    first_digest, _ = run_once(2026)
    second_digest, _ = run_once(2027)

    assert first_digest != second_digest
