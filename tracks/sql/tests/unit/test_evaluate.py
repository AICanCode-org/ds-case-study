"""06_evaluate.sql on a hand-made mini run: capacity, slices, fairness and the gate (20 customers, 2 months)."""

import pytest

from churncast_sql.runner import run_script, setvar, table
from tests.conftest import rows

VARS = {
    "calibration_bins": 10,
    "eps": 1e-15,
    "top_percent": 10,
    "offer_cost_inr": 200.0,
    "save_rate": 0.25,
    "value_months": 3.0,
    "min_slice_rows": 2,
    "min_slice_churners": 1,
    "fairness_dimension": "age_band",
    "fairness_min_churners": 1,
    "missing_label": "unknown",
    "leakage_limit": 0.9,
    "min_gain": 0.002,
    "gate_min_test_auc": 0.72,
    "gate_min_auc_uplift": 0.03,
    "gate_max_ece": 0.03,
    "gate_max_recall_gap": 0.15,
    "prior_id": "B0",
    "rule_id": "B1",
}


def mini(con, y: list[int], p: list[float]) -> None:
    for k, v in VARS.items():
        setvar(con, k, v)
    n = len(y)
    ids = [f"C{i:05d}" for i in range(n)]
    snaps = ["2026-03"] * (n // 2) + ["2026-04"] * (n - n // 2)
    bands = ["18-24", "25-34"] * (n // 2)
    table(
        con,
        "features",
        "customer_id VARCHAR, snapshot VARCHAR, split VARCHAR, churned INTEGER, a DOUBLE, price_inr DOUBLE, "
        "age_band VARCHAR, city_tier VARCHAR, plan VARCHAR, channel VARCHAR, city VARCHAR",
        [
            (ids[i], snaps[i], "test", y[i], p[i], 3000.0, bands[i], "tier1", "basic", "organic", "pune")
            for i in range(n)
        ],
    )
    con.execute("CREATE TABLE feature_long AS SELECT customer_id, snapshot, 'a' AS feature, a AS value FROM features")
    con.execute("CREATE TABLE customers AS SELECT customer_id, '' AS cancellation_reason FROM features")
    table(con, "cfg_features", "pos INTEGER, name VARCHAR", [(1, "a")])
    table(con, "cfg_slices", "pos INTEGER, dim VARCHAR", [(1, "age_band")])
    table(
        con,
        "cfg_experiments",
        "pos INTEGER, id VARCHAR, kind VARCHAR",
        [(1, "B0", "prior"), (2, "B1", "rule"), (3, "E1", "logistic")],
    )
    scored = []
    for exp, scores in (("B0", [0.15] * n), ("B1", [0.5 if i % 3 == 0 else 0.1 for i in range(n)]), ("E1", p)):
        for stage in ("cv0", "cv1", "test"):
            scored += [(exp, stage, ids[i], snaps[i], y[i], scores[i]) for i in range(n)]
    table(
        con,
        "scored",
        "exp_id VARCHAR, stage VARCHAR, customer_id VARCHAR, snapshot VARCHAR, y INTEGER, p DOUBLE",
        scored,
    )
    run_script(con, "05_metrics.sql")
    run_script(con, "06_evaluate.sql")


def test_contacted_is_the_top_decile_per_snapshot_with_ties_by_id(con):
    mini(con, [0] * 19 + [1], [0.5] * 20)
    got = rows(con, "SELECT customer_id FROM test_scored WHERE exp_id = 'E1' AND contacted ORDER BY customer_id")
    assert [r["customer_id"] for r in got] == ["C00000", "C00010"]


def test_capacity_metrics_and_value(con):
    y = [1 if i in (0, 10, 3) else 0 for i in range(20)]
    p = [0.9 if i in (0, 10) else 0.1 for i in range(20)]
    mini(con, y, p)
    m = rows(con, "SELECT * FROM capacity WHERE exp_id = 'E1'")[0]
    assert (m["contacted"], m["churners_reached"]) == (2, 2)
    assert m["precision_at_top"] == 1.0 and m["recall_at_top"] == pytest.approx(2 / 3)
    assert m["lift_at_top"] == pytest.approx(1 / (3 / 20))
    assert m["net_value_inr_per_month"] == pytest.approx((2 * 3000 * 0.25 * 3 - 2 * 200) / 2)


def test_slices_fairness_and_gate(con):
    y = [1 if i in (0, 1, 10, 11) else 0 for i in range(20)]
    p = [0.9 if i in (0, 10) else (0.8 if i in (1, 11) else 0.1) for i in range(20)]
    mini(con, y, p)
    by = {r["value"]: r for r in rows(con, "SELECT * FROM slices WHERE exp_id = 'E1'")}
    assert by["18-24"]["recall_at_top"] == 1.0 and by["25-34"]["recall_at_top"] == 0.0
    fair = rows(con, "SELECT * FROM fairness WHERE exp_id = 'E1'")[0]
    assert fair["recall_gap"] == 1.0 and fair["groups"] == ["18-24", "25-34"]
    failed = [r["id"] for r in rows(con, "SELECT id, passed FROM gate ORDER BY pos") if not r["passed"]]
    assert "recall_gap" in failed


def test_leakage_scan_flags_a_perfect_feature(con):
    y = [0] * 10 + [1] * 10
    mini(con, y, [i / 20 for i in range(20)])
    con.execute("UPDATE features SET split = 'train'")
    run_script(con, "06_evaluate.sql")
    leak = {r["name"]: r["auc"] for r in rows(con, "SELECT * FROM leakage")}
    assert leak["a"] == 1.0
    assert leak["cancellation_reason"] == 0.5
    assert rows(con, "SELECT passed FROM gate WHERE id = 'leakage_scan'") == [{"passed": False}]


def test_the_simpler_model_wins_a_tie(con):
    mini(con, [1 if i % 4 == 0 else 0 for i in range(20)], [0.9 if i % 4 == 0 else 0.1 for i in range(20)])
    assert rows(con, "SELECT champion_id FROM champion") == [{"champion_id": "E1"}]
