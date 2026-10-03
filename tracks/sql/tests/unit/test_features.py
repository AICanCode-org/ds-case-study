import math

from churncast_sql.runner import load_and_clean, run_script
from tests.conftest import EXPECTED, TINY, rows


def test_features_match_the_expected_tiny_table(tiny):
    got = rows(tiny, "SELECT * FROM features ORDER BY snapshot, customer_id")
    want = EXPECTED["features"]
    assert len(got) == len(want)
    for row, exp in zip(got, want, strict=True):
        for key, value in exp.items():
            if isinstance(value, float):
                assert math.isclose(row[key], value, rel_tol=1e-9, abs_tol=1e-12), (row["customer_id"], key)
            else:
                assert row[key] == value, (row["customer_id"], row["snapshot"], key)


def test_every_contract_feature_is_a_column(tiny, tiny_contract):
    cols = [r["column_name"] for r in rows(tiny, "DESCRIBE features")]
    names = [f["name"] for f in tiny_contract["features"]]
    assert cols[5 : 5 + len(names)] == names


def test_a_ticket_after_the_snapshot_is_invisible(tiny):
    """C00002 asks to cancel on 2 March: the February snapshot (cut-off 1 March) must not see it."""
    sql = "SELECT tickets_90d FROM features WHERE customer_id = 'C00002' AND snapshot = '2026-02'"
    assert tiny.execute(sql).fetchone()[0] == 1  # the billing ticket only


def test_the_label_needs_the_next_month(con, tiny_contract, export_copy):
    path = export_copy()
    meta = (path / "export.json").read_text(encoding="utf-8").replace('"2026-03"', '"2026-02"')
    (path / "export.json").write_text(meta, encoding="utf-8")
    load_and_clean(con, path, tiny_contract)
    run_script(con, "03_features.sql")
    labels = rows(con, "SELECT DISTINCT churned FROM features WHERE snapshot = '2026-02'")
    assert labels == [{"churned": None}]
    snap = rows(con, "SELECT churned, churn_rate FROM snapshots WHERE snapshot = '2026-02'")
    assert snap == [{"churned": None, "churn_rate": None}]


def test_folds_are_the_customer_number_mod_5(tiny):
    for r in rows(tiny, "SELECT customer_id, fold FROM features"):
        assert r["fold"] == int(r["customer_id"][1:]) % 5
    assert TINY.exists()


def test_snapshot_summary_counts_churners(tiny):
    for s in rows(tiny, "SELECT * FROM snapshots"):
        n = tiny.execute("SELECT count(*), sum(churned) FROM features WHERE snapshot = ?", [s["snapshot"]]).fetchone()
        assert (s["rows"], s["churned"]) == n
