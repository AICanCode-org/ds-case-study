import pytest

from churncast_sql.runner import ContractError, check_sql, ident, raise_on_errors, run_check, run_checks
from tests.conftest import EXPECTED


def check(**kw):
    base = {"id": "x", "table": "t", "severity": "error"}
    return {**base, **kw}


def make(con, sql: str):
    con.execute(f"CREATE OR REPLACE TABLE t AS {sql}")


def test_unique_counts_extra_rows(con):
    make(con, "SELECT * FROM (VALUES ('1'), ('1'), ('2'), ('2'), ('2')) v (a)")
    assert run_check(con, check(type="unique", column="a"))["failing_rows"] == 3


def test_unique_on_a_compound_key(con):
    make(con, "SELECT * FROM (VALUES ('1', 'x'), ('1', 'y')) v (a, b)")
    assert run_check(con, check(type="unique", column=["a", "b"]))["status"] == "pass"


def test_not_null_and_accepted_values(con):
    make(con, "SELECT * FROM (VALUES ('x'), (''), (' '), ('y'), (NULL)) v (a)")
    assert run_check(con, check(type="not_null", column="a"))["failing_rows"] == 3
    r = run_check(con, check(type="accepted_values", column="a", values=["x", "y"]))
    assert (r["failing_rows"], r["status"]) == (3, "fail")


def test_range_ignores_missing_values(con):
    make(con, "SELECT * FROM (VALUES (1.0), (NULL), (50.0), (-1.0)) v (a)")
    r = run_check(con, check(type="range", column="a", min=0, max=10))
    assert (r["failing_rows"], r["observed"]) == (2, 2 / 3)


def test_relationship(con):
    make(con, "SELECT * FROM (VALUES ('C1'), ('C9')) v (customer_id)")
    con.execute("CREATE TABLE customers AS SELECT 'C1' AS customer_id")
    assert run_check(con, check(type="relationship", column="customer_id", to="customers"))["failing_rows"] == 1


def test_max_ratio_is_a_share_and_warns(con):
    make(con, "SELECT * FROM (VALUES ('unknown'), ('x'), ('x'), ('x')) v (a)")
    r = run_check(con, check(type="max_ratio", column="a", value="unknown", max=0.2, severity="warn"))
    assert (r["failing_rows"], r["observed"], r["status"]) == (1, 0.25, "warn")


def test_the_tiny_export_passes_every_table_check(tiny, contract):
    results = run_checks(tiny, contract, {"customers", "invoices", "usage", "tickets", "raw_usage"})
    assert [r["id"] for r in results] == [c["id"] for c in contract["checks"] if c["table"] != "snapshots"]
    assert all(r["status"] != "fail" for r in results)
    assert EXPECTED["clean_rows"]["customers"] > 0


def test_errors_stop_the_run_warnings_do_not():
    raise_on_errors([{"id": "w", "status": "warn"}])
    with pytest.raises(ContractError, match="bad"):
        raise_on_errors([{"id": "bad", "status": "fail"}])


def test_only_plain_identifiers_reach_the_sql():
    assert ident("usage") == "usage"
    for bad in ["usage; DROP TABLE x", "Usage", "a-b", "", None]:
        with pytest.raises(ContractError):
            ident(bad)
    with pytest.raises(ContractError, match="unknown check type"):
        check_sql(check(type="regex", column="a"))
