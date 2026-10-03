import math

import pandas as pd
import pytest

from churncast import evaluate as ev
from tests.conftest import CASES

EV = {
    "top_percent": 10,
    "calibration_bins": 10,
    "offer_cost_inr": 200,
    "save_rate": 0.25,
    "value_months": 3,
    "slices": ["age_band"],
    "min_slice_rows_for_auc": 2,
    "min_slice_churners_for_auc": 1,
    "fairness": {"dimension": "age_band", "min_churners": 1, "max_recall_gap": 0.15},
}


@pytest.mark.parametrize("case", CASES["metric_cases"], ids=lambda c: c["name"])
def test_shared_metric_cases(case):
    y, s, p = case["y"], case["score"], case["prob"]
    assert ev.auc(y, s) == pytest.approx(case["auc"], abs=1e-12)
    assert ev.average_precision(y, s) == pytest.approx(case["average_precision"], abs=1e-12)
    assert ev.brier(y, p) == pytest.approx(case["brier"], abs=1e-12)
    assert ev.log_loss(y, p) == pytest.approx(case["log_loss"], abs=1e-12)
    cal = ev.calibration(y, p, 10)
    assert cal["ece"] == pytest.approx(case["ece"], abs=1e-12)
    assert [b["n"] for b in cal["bins"]] == [b["n"] for b in case["calibration_bins"]]


def test_auc_is_undefined_with_one_class():
    assert ev.auc([0, 0], [0.1, 0.2]) is None
    assert ev.average_precision([0, 0], [0.1, 0.2]) is None


def test_constant_scores_give_auc_one_half():
    assert ev.auc([0, 1, 0, 1], [0.3] * 4) == 0.5


@pytest.mark.parametrize("case", CASES["top_k"], ids=lambda c: str(c["n"]))
def test_top_k_rounds_up_without_floats(case):
    assert ev.top_k(case["n"], case["percent"]) == case["k"]


@pytest.mark.parametrize("case", CASES["quantile7"], ids=lambda c: str(c["q"]))
def test_quantile_type_7(case):
    assert ev.quantile7(case["values"], case["q"]) == pytest.approx(case["expected"], abs=1e-12)


def frame(n=20):
    return pd.DataFrame(
        {
            "snapshot": ["2026-03"] * (n // 2) + ["2026-04"] * (n - n // 2),
            "customer_id": [f"C{i:05d}" for i in range(n)],
            "price_inr": [3000.0] * n,
            "age_band": ["18-24", "25-34"] * (n // 2),
        }
    )


def test_contacted_is_the_top_decile_per_snapshot_with_ties_by_id():
    f = frame()
    p = [0.5] * 20
    c = ev.contacted(f, p, 10)
    assert list(f["customer_id"][c]) == ["C00000", "C00010"]


def test_capacity_metrics_and_value():
    f = frame()
    y = [1 if i in (0, 10, 3) else 0 for i in range(20)]
    p = [0.9 if i in (0, 10) else 0.1 for i in range(20)]
    m = ev.capacity_metrics(f, y, p, EV)
    assert (m["contacted"], m["churners_reached"]) == (2, 2)
    assert m["precision_at_top"] == 1.0 and m["recall_at_top"] == pytest.approx(2 / 3)
    assert m["lift_at_top"] == pytest.approx(1 / (3 / 20))
    assert m["net_value_inr_per_month"] == pytest.approx((2 * 3000 * 0.25 * 3 - 2 * 200) / 2)


def test_slices_fairness_and_gate():
    f = frame()
    y = [1 if i in (0, 1, 10, 11) else 0 for i in range(20)]
    p = [0.9 if i in (0, 10) else (0.8 if i in (1, 11) else 0.1) for i in range(20)]
    rows = ev.slices(f, y, p, EV)
    by = {r["value"]: r for r in rows["age_band"]}
    assert by["18-24"]["recall_at_top"] == 1.0 and by["25-34"]["recall_at_top"] == 0.0
    fair = ev.fairness(rows, EV, "unknown")
    assert fair["recall_gap"] == 1.0 and fair["passed"] is False
    g = ev.gate(
        {"auc": 0.8, "ece": 0.01, "brier": 0.07},
        {"auc": 0.7},
        {"brier": 0.08},
        fair,
        {"max_feature_auc": 0.7, "limit": 0.9, "passed": True},
        {"min_test_auc": 0.72, "min_auc_uplift_over_rule": 0.03, "max_ece": 0.03, "max_recall_gap": 0.15},
    )
    assert [c["id"] for c in g["checks"] if not c["passed"]] == ["recall_gap"] and g["passed"] is False


def test_leakage_scan_flags_a_perfect_feature():
    train = pd.DataFrame({"churned": [0, 0, 1, 1], "a": [1.0, 2.0, 3.0, 4.0], "b": [1.0, 0.0, 1.0, 0.0]})
    scan = ev.leakage_scan(train, ["a", "b"], [0, 0, 1, 1], 0.9)
    assert scan["max_feature"] == "a" and scan["passed"] is False
    assert scan["probe_auc"] == 1.0
    assert math.isclose(scan["feature_auc"]["b"], 0.5)
