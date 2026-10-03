"""v1.1: request ids, JSON access logs without personal data, Prometheus metrics, and serving 1.0 and 1.1 models."""

import json
import logging

from fastapi.testclient import TestClient

from churncast_api.app import create_app, default_paths
from churncast_api.explainer import Settings
from churncast_api.model import load_model
from churncast_api.observability import JsonFormatter, configure_logging, request_id_from
from tests.conftest import REPO


def test_a_safe_request_id_is_echoed_and_a_missing_one_generated(client, row):
    r = client.post("/v1/predict", headers={"X-Request-ID": "abc-123"}, json={"customers": [{"features": row}]})
    assert r.headers["X-Request-ID"] == "abc-123" and r.json()["request_id"] == "abc-123"
    r = client.get("/health")
    assert len(r.headers["X-Request-ID"]) == 32
    assert request_id_from("bad id\n") != "bad id\n" and request_id_from("x" * 65) != "x" * 65


def test_predict_and_explain_name_the_model_version(client, row):
    assert client.post("/v1/predict", json={"customers": [{"features": row}]}).json()["model_version"] == "1.1.0"
    d = client.post("/v1/explain", json={"features": row}).json()
    assert d["model_version"] == "1.1.0" and len(d["request_id"]) == 32


def test_access_logs_are_json_and_never_contain_the_body(client, row, caplog):
    caplog.set_level(logging.INFO, logger="churncast.access")
    client.post(
        "/v1/predict",
        headers={"X-Request-ID": "req-7"},
        json={"customers": [{"customer_id": "SECRET-42", "features": row}]},
    )
    records = [r for r in caplog.records if r.name == "churncast.access"]
    assert len(records) == 1
    line = json.loads(JsonFormatter().format(records[0]))
    assert line["request_id"] == "req-7" and line["route"] == "/v1/predict" and line["status"] == 200
    assert line["method"] == "POST" and line["duration_ms"] >= 0 and line["level"] == "info"
    assert "SECRET-42" not in caplog.text and "tenure_months" not in caplog.text


def test_unknown_urls_are_logged_by_route_not_by_path(client, caplog):
    caplog.set_level(logging.INFO, logger="churncast.access")
    assert client.get("/customers/C00042/secret").status_code == 404
    assert "C00042" not in caplog.text
    assert 'route="unmatched",status="404"' in client.get("/metrics").text


def test_metrics_in_prometheus_text_format(client, row):
    client.post("/v1/predict", json={"customers": [{"features": row}] * 3})
    client.post("/v1/explain", json={"features": row})
    r = client.get("/metrics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain; version=0.0.4")
    text = r.text
    assert 'churncast_model_info{model_version="1.1.0",schema_version="1.1",track="python"} 1' in text
    assert 'churncast_requests_total{method="POST",route="/v1/predict",status="200"} 1' in text
    assert "churncast_predictions_total 4" in text
    assert 'churncast_request_duration_seconds_bucket{route="/v1/predict",le="+Inf"} 1' in text
    assert "# TYPE churncast_request_duration_seconds histogram" in text


def test_explainer_fallbacks_are_counted(model, row):
    c = TestClient(create_app(model, Settings(provider="llm", base_url="http://10.255.255.1:9", timeout_ms=200)))
    d = c.post("/v1/explain", json={"features": row}).json()
    assert d["explanation"]["fallback"] is True
    assert 'churncast_explainer_fallbacks_total{reason="provider unreachable"} 1' in c.get("/metrics").text


def test_the_v1_0_artefact_still_serves(row):
    p = default_paths()
    old = load_model(REPO / "models" / "churncast-1.0.0.json", p["contract"], p["schema"])
    c = TestClient(create_app(old, Settings()))
    assert c.get("/health").json()["model_version"] == "1.0.0"
    assert c.post("/v1/predict", json={"customers": [{"features": row}]}).json()["model_version"] == "1.0.0"


def test_configure_logging_writes_json(capsys):
    configure_logging()
    logging.getLogger("churncast.test").info("hello", extra={"request_id": "r1"})
    line = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert line["msg"] == "hello" and line["request_id"] == "r1"
