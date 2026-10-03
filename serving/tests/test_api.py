from churncast_api.app import MAX_BATCH, create_app


def test_health_and_model(client, model):
    assert client.get("/health").json() == {"status": "ok", "model_version": "1.1.0"}
    m = client.get("/v1/model").json()
    assert [f["name"] for f in m["features"]] == model.features
    assert m["explainer"] == {"provider": "offline"}
    assert 0 < m["high_risk_threshold"] < 1


def test_predict_a_batch(client, row):
    r = client.post("/v1/predict", json={"customers": [{"customer_id": "A1", "features": row}, {"features": row}]})
    assert r.status_code == 200
    preds = r.json()["predictions"]
    assert [p["customer_id"] for p in preds] == ["A1", None]
    assert 0 < preds[0]["churn_probability"] < 1 and preds[0]["risk_band"] in ("high", "normal")
    assert len(preds[0]["top_reasons"]) == 3


def test_invalid_input_is_a_problem_json_422(client, row):
    r = client.post("/v1/predict", json={"customers": [{"features": {**row, "tenure_months": 999}}, 7]})
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
    fields = [e["field"] for e in r.json()["errors"]]
    assert fields == ["customers[0].features.tenure_months", "customers[1]"]
    assert client.post("/v1/predict", json={"customers": []}).status_code == 422
    assert client.post("/v1/predict", json=[1]).status_code == 422
    assert client.post("/v1/predict", content=b"{nope", headers={"Content-Type": "application/json"}).status_code == 400
    long_id = {"customers": [{"customer_id": "x" * 65, "features": row}]}
    assert client.post("/v1/predict", json=long_id).json()["errors"][0]["field"] == "customers[0].customer_id"


def test_the_batch_limit(client, row):
    r = client.post("/v1/predict", json={"customers": [{"features": row}] * (MAX_BATCH + 1)})
    assert r.status_code == 413


def test_explain(client, row):
    r = client.post("/v1/explain", json={"features": row})
    assert r.status_code == 200
    d = r.json()
    assert d["explanation"]["source"] == "template" and d["explanation"]["fallback"] is False
    assert "[R1]" in d["explanation"]["text"]
    assert client.post("/v1/explain", json={"features": {}}).status_code == 422
    assert client.post("/v1/explain", content=b"[", headers={"Content-Type": "application/json"}).status_code == 400


def test_the_form_page(client):
    r = client.get("/")
    assert r.status_code == 200 and "ChurnCast" in r.text


def test_the_app_loads_the_default_model(monkeypatch):
    monkeypatch.delenv("MODEL_PATH", raising=False)
    from fastapi.testclient import TestClient

    assert TestClient(create_app()).get("/health").json()["model_version"] == "1.1.0"
