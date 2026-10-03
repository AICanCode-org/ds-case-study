"""A broken export must stop the run with exit code 3, never train a model on it."""

import pytest

from churncast_sql.__main__ import main
from tests.conftest import EXPORT_V10


@pytest.fixture
def broken(export_copy):
    return export_copy(EXPORT_V10)


def run(path, tmp_path):
    return main(["run", "--data", str(path), "--out", str(tmp_path / "out")])


def test_an_unknown_plan(broken, tmp_path, capsys):
    with open(broken / "invoices.csv", "a", encoding="utf-8") as fh:
        fh.write("INV9999999,C00010,2026-05,charge,platinum,5999,0,paid\n")
    assert run(broken, tmp_path) == 3
    assert "invoices.plan.accepted" in capsys.readouterr().err


def test_a_reused_invoice_id(broken, tmp_path, capsys):
    with open(broken / "invoices.csv", "a", encoding="utf-8") as fh:
        fh.write("INV0000001,C00010,2026-05,charge,basic,2499,0,paid\n")
    assert run(broken, tmp_path) == 3
    assert "invoices.invoice_id.unique" in capsys.readouterr().err


def test_a_broken_billing_export_with_no_renewals(broken, tmp_path, capsys):
    """If April's invoices are lost, every March customer looks like a churner: the churn-rate check stops it."""
    lines = (broken / "invoices.csv").read_text(encoding="utf-8").splitlines(keepends=True)
    (broken / "invoices.csv").write_text("".join(x for x in lines if ",2026-04," not in x), encoding="utf-8")
    assert run(broken, tmp_path) == 3
    assert "snapshots.churn_rate.range" in capsys.readouterr().err


def test_an_impossible_meal_count(broken, tmp_path, capsys):
    with open(broken / "usage.csv", "a", encoding="utf-8") as fh:
        fh.write("C00010,2026-06,99,0,0,0,0\n")
    assert run(broken, tmp_path) == 3
    assert "usage.meals_ordered.range" in capsys.readouterr().err
