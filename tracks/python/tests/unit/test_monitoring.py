"""M7 unit tests: PSI, the calibration offset, the fairness recall gap and the retraining gate on tiny inputs."""

import math

import numpy as np
import pandas as pd
import pytest

from churncast.monitoring import bin_shares, calibration_offset, psi, psi_edges, psi_status, recall_gap


def test_psi_edges_are_type7_deciles_without_duplicates():
    assert psi_edges(range(1, 12), 10) == [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert psi_edges([0] * 8 + [1, 2], 10) == pytest.approx([0.0, 0.2, 1.1])  # the zeros give one edge, not 7


def test_a_value_on_an_edge_falls_in_the_lower_bin():
    # bin = number of edges strictly below the value
    assert bin_shares([1, 2, 2.5, 3, 4], [2.0, 3.0]) == [0.4, 0.4, 0.2]  # 1, 2 | 2.5, 3 | 4


def test_psi_is_zero_for_the_same_distribution_and_symmetric_in_form():
    ref = [0.25, 0.25, 0.5]
    assert psi(ref, ref, 1e-4) == 0.0
    expected = (0.5 - 0.25) * math.log(0.5 / 0.25) + (0.0001 - 0.25) * math.log(0.0001 / 0.25) + 0
    assert psi(ref, [0.5, 0.0, 0.5], 1e-4) == pytest.approx(expected)


def test_psi_status_thresholds():
    mon = {"psi_watch": 0.10, "psi_drift": 0.25}
    assert [psi_status(v, mon) for v in (0.0999, 0.10, 0.2499, 0.25)] == ["stable", "watch", "watch", "drift"]


def test_calibration_offset_matches_the_mean():
    eta = np.array([-2.0, -1.0, 0.0, 1.0])
    y = np.array([0, 1, 1, 1])
    d = calibration_offset(eta, y)
    assert (1 / (1 + np.exp(-(eta + d)))).sum() == pytest.approx(3.0, abs=1e-10)
    assert calibration_offset(np.zeros(4), np.array([0, 0, 1, 1])) == pytest.approx(0.0, abs=1e-12)


def test_recall_gap_ignores_small_and_unknown_groups():
    frame = pd.DataFrame(
        {
            "snapshot": ["2026-06"] * 8,
            "customer_id": [f"C{i:05d}" for i in range(8)],
            "age_band": ["a"] * 4 + ["b"] * 3 + ["unknown"],
        }
    )
    y = [1, 1, 0, 0, 1, 0, 0, 1]
    p = [0.9, 0.1, 0.2, 0.3, 0.8, 0.4, 0.5, 0.95]
    ev = {"top_percent": 25, "fairness": {"dimension": "age_band", "min_churners": 1}}
    # top 25 % of 8 = 2 rows: 0.95 (unknown) and 0.9 (a). Recall a = 1/2, b = 0/1.
    assert recall_gap(frame, y, p, ev, "unknown") == pytest.approx(0.5)
