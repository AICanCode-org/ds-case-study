import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from churncast_api.app import create_app, default_paths
from churncast_api.explainer import Settings
from churncast_api.model import load_model

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def model():
    p = default_paths()
    return load_model(p["model"], p["contract"], p["schema"])


@pytest.fixture
def row(model):
    """A typical subscriber: every feature at a valid value."""
    return {
        "tenure_months": 2,
        "is_new": 1,
        "plan_standard": 1,
        "plan_premium": 0,
        "discount_share": 0.2,
        "price_change_pct": 0.0,
        "meals_last_month": 9,
        "skip_rate_last_month": 0.35,
        "meals_trend": -6.0,
        "late_rate_3m": 0.12,
        "avg_rating_3m": 3.4,
        "rating_missing": 0,
        "tickets_90d": 2,
        "open_tickets": 1,
        "failed_payments_3m": 1,
    }


@pytest.fixture
def client(model):
    return TestClient(create_app(model, Settings()))


@pytest.fixture
def artefact_copy(tmp_path):
    def make(edit) -> Path:
        a = json.loads((REPO / "models" / "churncast-1.0.0.json").read_text(encoding="utf-8"))
        edit(a)
        path = tmp_path / "model.json"
        path.write_text(json.dumps(a), encoding="utf-8")
        return path

    return make
