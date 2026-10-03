import pandas as pd
import pytest

from churncast.checks import raise_on_errors, run_check, run_checks
from churncast.contract import ContractError


def check(**kw):
    base = {"id": "x", "table": "t", "severity": "error"}
    return {**base, **kw}


def test_unique_counts_extra_rows():
    t = {"t": pd.DataFrame({"a": ["1", "1", "2", "2", "2"]})}
    assert run_check(check(type="unique", column="a"), t)["failing_rows"] == 3


def test_unique_on_a_compound_key():
    t = {"t": pd.DataFrame({"a": ["1", "1"], "b": ["x", "y"]})}
    assert run_check(check(type="unique", column=["a", "b"]), t)["status"] == "pass"


def test_not_null_and_accepted_values():
    t = {"t": pd.DataFrame({"a": ["x", "", " ", "y"]})}
    assert run_check(check(type="not_null", column="a"), t)["failing_rows"] == 2
    r = run_check(check(type="accepted_values", column="a", values=["x", "y"]), t)
    assert (r["failing_rows"], r["status"]) == (2, "fail")


def test_range_ignores_missing_values_but_not_garbage():
    t = {"t": pd.DataFrame({"a": [1.0, None, 50.0, "abc"]})}
    assert run_check(check(type="range", column="a", min=0, max=10), t)["failing_rows"] == 2


def test_relationship():
    t = {"t": pd.DataFrame({"customer_id": ["C1", "C9"]}), "customers": pd.DataFrame({"customer_id": ["C1"]})}
    assert run_check(check(type="relationship", column="customer_id", to="customers"), t)["failing_rows"] == 1


def test_max_ratio_is_a_share_and_warns():
    t = {"t": pd.DataFrame({"a": ["unknown", "x", "x", "x"]})}
    r = run_check(check(type="max_ratio", column="a", value="unknown", max=0.2, severity="warn"), t)
    assert (r["failing_rows"], r["observed"], r["status"]) == (1, 0.25, "warn")


def test_the_tiny_export_passes_every_table_check(contract, tiny):
    raw, tables, _ = tiny
    results = run_checks(
        contract, {**tables, "raw_usage": raw["usage"]}, only={"customers", "invoices", "usage", "tickets", "raw_usage"}
    )
    assert [r["id"] for r in results] == [c["id"] for c in contract["checks"] if c["table"] != "snapshots"]
    assert all(r["status"] != "fail" for r in results)


def test_errors_stop_the_run_warnings_do_not():
    raise_on_errors([{"id": "w", "status": "warn"}])
    with pytest.raises(ContractError, match="bad"):
        raise_on_errors([{"id": "bad", "status": "fail"}])
