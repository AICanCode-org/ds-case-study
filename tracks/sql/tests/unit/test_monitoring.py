"""M7 unit tests for the macros of 07_monitoring.sql: PSI edges, bin shares, and the Newton calibration offset."""

import math

import pytest

from churncast_sql.runner import calibration_offset, run_script, setvar, table


@pytest.fixture
def mon(con):
    run_script(con, "05_metrics.sql")
    # 07 also creates tables from post_scored: give it empty inputs so only the macros matter here
    con.execute(
        "CREATE TABLE post_scored (model VARCHAR, customer_id VARCHAR, snapshot VARCHAR, split VARCHAR, y INTEGER, "
        "p DOUBLE)"
    )
    con.execute(
        "CREATE TABLE feature_long (customer_id VARCHAR, snapshot VARCHAR, split VARCHAR, fold INTEGER, "
        "churned INTEGER, feature VARCHAR, value DOUBLE)"
    )
    con.execute(
        "CREATE TABLE features (customer_id VARCHAR, snapshot VARCHAR, split VARCHAR, churned INTEGER, "
        "price_inr DOUBLE, age_band VARCHAR, city_tier VARCHAR, plan VARCHAR, channel VARCHAR, city VARCHAR)"
    )
    table(con, "cfg_model_features", "model VARCHAR, name VARCHAR", [])
    table(con, "cfg_profile_splits", "split VARCHAR", [("train",)])
    for name, value in {
        "psi_floor": 1e-4,
        "psi_watch": 0.1,
        "psi_drift": 0.25,
        "alert_max_ece": 0.03,
        "alert_max_mean_gap": 0.02,
        "alert_min_auc": 0.72,
        "rt_max_auc_drop": 0.005,
        "rt_max_ece": 0.03,
        "rt_max_recall_gap": 0.15,
        "top_percent": 10,
        "fairness_dimension": "age_band",
        "fairness_min_churners": 30,
        "missing_label": "unknown",
        "save_rate": 0.25,
        "value_months": 3.0,
        "offer_cost_inr": 200.0,
        "calibration_bins": 10,
        "eps": 1e-15,
    }.items():
        setvar(con, name, value)
    run_script(con, "07_monitoring.sql")
    return con


def test_psi_edges_are_type7_deciles_without_duplicates(mon):
    mon.execute("CREATE TABLE t AS SELECT 'x' AS var, CAST(range AS DOUBLE) AS value FROM range(1, 12)")
    mon.execute("INSERT INTO t SELECT 'z', CASE WHEN range < 8 THEN 0 ELSE range - 7 END FROM range(10)")
    edges = mon.execute(
        "SELECT var, list(edge ORDER BY edge) FROM psi_edges_of(t) GROUP BY var ORDER BY var"
    ).fetchall()
    assert edges[0] == ("x", [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    assert edges[1][1] == pytest.approx([0.0, 0.2, 1.1])


def test_a_value_on_an_edge_falls_in_the_lower_bin(mon):
    mon.execute("CREATE TABLE v AS SELECT 'g' AS grp, 'x' AS var, unnest([1, 2, 2.5, 3, 4]) AS value")
    mon.execute("CREATE TABLE e AS SELECT 'x' AS var, unnest([2.0, 3.0]) AS edge")
    got = mon.execute("SELECT bin, share FROM bin_shares_of(v, e) ORDER BY bin").fetchall()
    assert got == [(0, 0.4), (1, 0.4), (2, 0.2)]


def test_empty_bins_are_kept(mon):
    mon.execute("CREATE TABLE v AS SELECT 'g' AS grp, 'x' AS var, unnest([5.0, 6.0]) AS value")
    mon.execute("CREATE TABLE e AS SELECT 'x' AS var, unnest([2.0, 3.0]) AS edge")
    assert mon.execute("SELECT list(share ORDER BY bin) FROM bin_shares_of(v, e)").fetchone()[0] == [0.0, 0.0, 1.0]


def test_calibration_offset_matches_the_mean(con):
    con.execute(
        "CREATE TABLE features AS SELECT unnest([-2.0, -1.0, 0.0, 1.0]) AS a, unnest([0, 1, 1, 1]) AS churned, "
        "'recent' AS split"
    )
    d = calibration_offset(con, {"intercept": 0.0, "coefficients": {"a": 1.0}}, "recent")
    total = sum(1 / (1 + math.exp(-(a + d))) for a in (-2.0, -1.0, 0.0, 1.0))
    assert total == pytest.approx(3.0, abs=1e-10)
