import json
import shutil
from pathlib import Path

import pytest

from churncast_sql.runner import connect, load_and_clean, load_contract, run_script

# ---------------------------------------------------------------------------
# PENDING tests describe behaviour you have not built yet, so they are skipped
# (reported as "s" by pytest). When you start a milestone, delete its line here,
# watch the tests fail (red), implement until they pass (green). See docs/phase-3.
# ---------------------------------------------------------------------------
PENDING: dict[str, str] = {
    "test_load.py": "Phase 3 M1 - load the raw export as text",
    "test_clean.py": "Phase 3 M1 - cleaning rules and the issue counts",
    "test_checks.py": "Phase 3 M2 - data-contract checks",
    "test_features.py": "Phase 3 M3 - point-in-time features and labels",
    "test_model.py": "Phase 3 M4 - baselines, logistic regression, grouped folds",
    "test_metrics.py": "Phase 3 M4 - AUC, AP, Brier, calibration, top-k by hand",
    "test_evaluate.py": "Phase 3 M5 - evaluation tables on a mini run",
    "test_artefact.py": "Phase 3 M5 - the model artefact and explanations",
    "test_cli.py": "Phase 3 M5 - command line and exit codes",
    "test_golden.py": "Phase 4 - golden metrics and model on the real export",
    "test_invariants.py": "Phase 4 - invariants on the real export",
    "test_leakage.py": "Phase 4 - leakage: point-in-time and banned columns",
    "test_contract_violations.py": "Phase 4 - contract violations stop the run",
    "test_model_quality.py": "Phase 4 - model quality and the gate",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        reason = PENDING.get(item.path.name)
        if reason:
            item.add_marker(pytest.mark.skip(reason=f"PENDING ({reason}) - see tests/conftest.py"))


REPO = Path(__file__).resolve().parents[3]
CONTRACT_DIR = REPO / "contract"
TINY = CONTRACT_DIR / "fixtures" / "tiny"
EXPORT_V10 = REPO / "data" / "raw" / "2026-05"
EXPECTED = json.loads((CONTRACT_DIR / "fixtures" / "tiny-expected.json").read_text(encoding="utf-8"))
CASES = json.loads((CONTRACT_DIR / "fixtures" / "metric-cases.json").read_text(encoding="utf-8"))


def rows(con, sql: str, params: list | None = None) -> list[dict]:
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


@pytest.fixture(scope="session")
def contract():
    return load_contract()


@pytest.fixture
def tiny_contract(contract):
    """The shared contract with the tiny export's snapshots (see tiny-expected.json)."""
    c = json.loads(json.dumps(contract))
    c["snapshots"].update(EXPECTED["snapshots"])
    return c


@pytest.fixture
def con():
    c = connect()
    yield c
    c.close()


@pytest.fixture
def tiny(con, tiny_contract):
    """A connection with the tiny export loaded, cleaned and turned into features (01-03)."""
    load_and_clean(con, TINY, tiny_contract)
    run_script(con, "03_features.sql")
    return con


@pytest.fixture
def export_copy(tmp_path):
    """A writable copy of an export folder, to corrupt on purpose."""

    def make(source: Path = TINY) -> Path:
        target = tmp_path / source.name
        shutil.copytree(source, target)
        return target

    return make


@pytest.fixture(scope="session")
def run(contract):
    """The whole pipeline on the real 2026-05 export (about 3 s, once per test session): (connection, result)."""
    from churncast_sql.runner import analyse

    c = connect()
    result = analyse(c, EXPORT_V10, contract)
    yield c, result
    c.close()


@pytest.fixture(scope="session")
def result(run):
    return run[1]
