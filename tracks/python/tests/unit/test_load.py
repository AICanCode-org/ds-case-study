import pytest

from churncast.contract import ContractError
from churncast.load import load_export_meta, load_raw
from tests.conftest import EXPECTED, TINY


def test_every_file_is_read_as_text(contract):
    raw = load_raw(TINY, contract)
    assert {k: len(v) for k, v in raw.items()} == EXPECTED["raw_rows"]
    assert all(isinstance(v, str) for df in raw.values() for v in df.to_numpy().ravel())
    assert raw["customers"].loc[2, "acquisition_channel"] == ""  # empty stays empty, never NaN


def test_columns_come_in_contract_order(contract):
    raw = load_raw(TINY, contract)
    for name, spec in contract["files"].items():
        assert list(raw[name].columns) == spec["columns"]


def test_a_missing_file_is_a_contract_error(contract, export_copy):
    path = export_copy()
    (path / "usage.csv").unlink()
    with pytest.raises(ContractError, match=r"usage\.csv"):
        load_raw(path, contract)


def test_a_missing_column_is_a_contract_error(contract, export_copy):
    path = export_copy()
    text = (path / "tickets.csv").read_text(encoding="utf-8").replace("resolved_at", "closed_at", 1)
    (path / "tickets.csv").write_text(text, encoding="utf-8")
    with pytest.raises(ContractError, match="resolved_at"):
        load_raw(path, contract)


def test_export_metadata(export_copy):
    assert load_export_meta(TINY)["export"] == "2026-03"
    path = export_copy()
    (path / "export.json").unlink()
    with pytest.raises(ContractError):
        load_export_meta(path)
