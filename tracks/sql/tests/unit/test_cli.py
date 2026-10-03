from churncast_sql.__main__ import main
from tests.conftest import TINY


def test_missing_export_is_an_io_error(tmp_path, capsys):
    assert main(["run", "--data", str(tmp_path / "nope"), "--out", str(tmp_path / "out")]) == 2
    assert "no export folder" in capsys.readouterr().err


def test_a_broken_contract_value_exits_3(export_copy, tmp_path, capsys):
    path = export_copy()
    with open(path / "customers.csv", "a", encoding="utf-8") as fh:
        fh.write("C00007,2026-01-05,Mumbai,organic,25-34,\n")
    assert main(["run", "--data", str(path), "--out", str(tmp_path / "out")]) == 3
    assert "customers.city.accepted" in capsys.readouterr().err


def test_unreadable_contract_file_exits_2(tmp_path, capsys):
    code = main(["run", "--data", str(TINY), "--out", str(tmp_path), "--contract", str(tmp_path / "missing.yaml")])
    assert code == 2
