import pytest

from churncast_sql.runner import ContractError, load_and_clean, load_export
from tests.conftest import EXPECTED, TINY, rows


def test_every_file_is_read_as_text(con, contract):
    load_and_clean(con, TINY, contract)
    for table, n in EXPECTED["raw_rows"].items():
        assert con.execute(f"SELECT count(*) FROM raw_{table}").fetchone()[0] == n
        types = {r["column_type"] for r in rows(con, f"DESCRIBE raw_{table}")}
        assert types == {"VARCHAR"}
    blank = con.execute("SELECT acquisition_channel FROM raw_customers LIMIT 1 OFFSET 2").fetchone()[0]
    assert blank == ""  # empty stays empty, never NULL


def test_columns_come_in_contract_order(con, contract):
    load_and_clean(con, TINY, contract)
    for name, spec in contract["files"].items():
        assert [r["column_name"] for r in rows(con, f"DESCRIBE raw_{name}")] == spec["columns"]


def test_a_missing_file_is_a_contract_error(con, contract, export_copy):
    path = export_copy()
    (path / "usage.csv").unlink()
    with pytest.raises(ContractError, match=r"usage\.csv"):
        load_and_clean(con, path, contract)


def test_a_missing_column_is_a_contract_error(con, contract, export_copy):
    path = export_copy()
    text = (path / "tickets.csv").read_text(encoding="utf-8").replace("resolved_at", "closed_at", 1)
    (path / "tickets.csv").write_text(text, encoding="utf-8")
    with pytest.raises(ContractError, match="resolved_at"):
        load_and_clean(con, path, contract)


def test_export_metadata(export_copy):
    assert load_export(TINY)["export"] == "2026-03"
    path = export_copy()
    (path / "export.json").unlink()
    with pytest.raises(ContractError):
        load_export(path)


def test_unsupported_date_formats_are_refused(con, contract):
    c = {**contract, "cleaning": {**contract["cleaning"], "date_formats": ["%m/%d/%Y"]}}
    with pytest.raises(ContractError, match="formats"):
        load_and_clean(con, TINY, c)
