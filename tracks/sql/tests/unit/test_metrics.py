import pytest

from churncast_sql.runner import run_script, setvar, table
from tests.conftest import CASES, rows


@pytest.fixture
def metrics(con):
    setvar(con, "calibration_bins", 10)
    setvar(con, "eps", 1e-15)
    run_script(con, "05_metrics.sql")
    return con


def load_case(con, name: str, y: list, p: list) -> None:
    table(con, "cases", "grp VARCHAR, y INTEGER, p DOUBLE", [(name, a, b) for a, b in zip(y, p, strict=True)])


@pytest.mark.parametrize("case", CASES["metric_cases"], ids=lambda c: c["name"])
def test_shared_metric_cases(metrics, case):
    load_case(metrics, case["name"], case["y"], case["score"])
    assert metrics.execute("SELECT auc FROM auc_of(cases)").fetchone()[0] == pytest.approx(case["auc"], abs=1e-12)
    ap = metrics.execute("SELECT average_precision FROM ap_of(cases)").fetchone()[0]
    assert ap == pytest.approx(case["average_precision"], abs=1e-12)
    load_case(metrics, case["name"], case["y"], case["prob"])
    s = rows(metrics, "SELECT brier, log_loss, ece FROM probability_scores_of(cases)")[0]
    assert s["brier"] == pytest.approx(case["brier"], abs=1e-12)
    assert s["log_loss"] == pytest.approx(case["log_loss"], abs=1e-12)
    assert s["ece"] == pytest.approx(case["ece"], abs=1e-12)
    bins = [r["n"] for r in rows(metrics, "SELECT n FROM calibration_of(cases) ORDER BY bin")]
    assert bins == [b["n"] for b in case["calibration_bins"]]


def test_auc_is_undefined_with_one_class(metrics):
    load_case(metrics, "g", [0, 0], [0.1, 0.2])
    assert metrics.execute("SELECT auc FROM auc_of(cases)").fetchone()[0] is None
    assert metrics.execute("SELECT average_precision FROM ap_of(cases)").fetchone()[0] is None


def test_constant_scores_give_auc_one_half(metrics):
    load_case(metrics, "g", [0, 1, 0, 1], [0.3] * 4)
    assert metrics.execute("SELECT auc FROM auc_of(cases)").fetchone()[0] == 0.5


def test_one_result_row_per_group(metrics):
    table(
        metrics,
        "cases",
        "grp VARCHAR, y INTEGER, p DOUBLE",
        [("a", 0, 0.1), ("a", 1, 0.9), ("b", 1, 0.2), ("b", 0, 0.8)],
    )
    assert rows(metrics, "SELECT grp, auc FROM auc_of(cases) ORDER BY grp") == [
        {"grp": "a", "auc": 1.0},
        {"grp": "b", "auc": 0.0},
    ]


@pytest.mark.parametrize("case", CASES["top_k"], ids=lambda c: str(c["n"]))
def test_top_k_rounds_up_without_floats(metrics, case):
    assert metrics.execute("SELECT top_k(?, ?)", [case["n"], case["percent"]]).fetchone()[0] == case["k"]


@pytest.mark.parametrize("case", CASES["quantile7"], ids=lambda c: str(c["q"]))
def test_quantile_type_7(con, case):
    table(con, "v", "x DOUBLE", [(x,) for x in case["values"]])
    got = con.execute("SELECT quantile_cont(x, ?) FROM v", [case["q"]]).fetchone()[0]
    assert got == pytest.approx(case["expected"], abs=1e-12)
