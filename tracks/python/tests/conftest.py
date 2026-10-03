import json
import shutil
from pathlib import Path

import pytest

from churncast.clean import clean_tables
from churncast.contract import load_contract
from churncast.load import load_raw

# ---------------------------------------------------------------------------
# PENDING tests describe behaviour you have not built yet, so they are skipped
# (reported as "s" by pytest). When you start a milestone, delete its line here,
# watch the tests fail (red), implement until they pass (green). See docs/phase-3.
# ---------------------------------------------------------------------------
PENDING: dict[str, str] = {}


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
def tiny(tiny_contract):
    raw = load_raw(TINY, tiny_contract)
    tables, issues = clean_tables(raw, tiny_contract)
    return raw, tables, issues


@pytest.fixture
def export_copy(tmp_path):
    """A writable copy of an export folder, to corrupt on purpose."""

    def make(source: Path = TINY) -> Path:
        target = tmp_path / source.name
        shutil.copytree(source, target)
        return target

    return make


@pytest.fixture(scope="session")
def result(contract):
    """The whole pipeline on the real 2026-05 export (about 3 s, computed once per test session)."""
    from churncast.pipeline import analyse

    return analyse(EXPORT_V10, contract)
