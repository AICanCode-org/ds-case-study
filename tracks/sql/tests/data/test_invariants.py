"""Properties that must hold for ANY export, not just this one."""

from tests.conftest import rows


def test_rows_read_equal_rows_kept_plus_rows_dropped(result):
    dq = result["metrics"]["data_quality"]
    raw, clean, issues = dq["raw_rows"], dq["clean_rows"], dq["issues"]
    dropped = {
        "customers": issues["customers_invalid_signup_date"] + issues["customers_exact_duplicates"],
        "invoices": issues["invoices_exact_duplicates"] + issues["invoices_orphans"],
        "usage": issues["usage_exact_duplicates"] + issues["usage_negative_counts"] + issues["usage_orphans"],
        "tickets": issues["tickets_invalid_created_at"] + issues["tickets_orphans"],
    }
    for table in raw:
        assert raw[table] == clean[table] + dropped[table], table


def test_every_feature_is_inside_its_contract_range(run, contract):
    con, _ = run
    for spec in contract["features"]:
        name = spec["name"]
        bad = con.execute(
            f"SELECT count(*) FROM features WHERE {name} IS NULL OR {name} < ? OR {name} > ?",
            [spec["min"], spec["max"]],
        ).fetchone()[0]
        assert bad == 0, name
        if spec["type"] == "binary":
            values = {r[name] for r in rows(con, f"SELECT DISTINCT {name} FROM features")}
            assert values <= {0.0, 1.0}, name


def test_one_row_per_customer_and_snapshot(run):
    con, _ = run
    n, distinct = con.execute("SELECT count(*), count(DISTINCT (customer_id, snapshot)) FROM features").fetchone()
    assert n == distinct


def test_no_customer_sits_in_two_folds_and_test_comes_after_train(result):
    m = result["metrics"]
    assert m["split"]["customers_in_two_folds"] == 0
    assert max(m["split"]["train_snapshots"]) < min(m["split"]["test_snapshots"])
    assert sum(f["rows"] for f in m["split"]["folds"]) == m["split"]["train_rows"]


def test_labels_exist_for_every_train_and_test_row(run):
    con, _ = run
    assert (
        con.execute("SELECT count(*) FROM features WHERE split IN ('train', 'test') AND churned IS NULL").fetchone()[0]
        == 0
    )


def test_every_cv_row_is_scored_exactly_once_per_experiment(run, result):
    con, _ = run
    for exp in ("B0", "B1", "E1", "E2"):
        n, distinct = con.execute(
            "SELECT count(*), count(DISTINCT (customer_id, snapshot)) FROM scored "
            "WHERE exp_id = ? AND stage LIKE 'cv%'",
            [exp],
        ).fetchone()
        assert n == distinct == result["metrics"]["split"]["train_rows"], exp
