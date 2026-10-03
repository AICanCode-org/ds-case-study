"""ChurnCast prediction API (v1.0).

GET  /health         liveness + which model is loaded
GET  /v1/model       the model card in JSON: features (with units and allowed ranges), threshold, test metrics
POST /v1/predict     up to MAX_BATCH customers -> churn probability, risk band, top 3 reasons
POST /v1/explain     one customer -> probability + a plain-language note (template, or optional AI explainer)
GET  /               a small HTML form to try it

Invalid input gets 422 application/problem+json listing every problem. Customer ids are opaque labels echoed back;
they are never logged and never sent to the AI provider.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from . import __version__
from .explainer import Settings, explain
from .model import Model, load_model

MAX_BATCH = 1000
ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parents[1] / "static"
log = logging.getLogger("churncast.api")


def default_paths() -> dict[str, str]:
    return {
        "model": os.environ.get("MODEL_PATH", str(ROOT / "models" / "churncast-1.0.0.json")),
        "contract": os.environ.get("CONTRACT_PATH", str(ROOT / "contract" / "data-contract.yaml")),
        "schema": os.environ.get("MODEL_SCHEMA_PATH", str(ROOT / "contract" / "model.schema.json")),
    }


def problem(status: int, title: str, errors: list[dict] | None = None) -> JSONResponse:
    body = {"type": "about:blank", "title": title, "status": status}
    if errors is not None:
        body["errors"] = errors[:50]
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def create_app(model: Model | None = None, settings: Settings | None = None) -> FastAPI:
    if model is None:
        p = default_paths()
        model = load_model(p["model"], p["contract"], p["schema"])
    ai = settings or Settings.from_env()
    app = FastAPI(title="ChurnCast API", version=__version__, docs_url="/docs", redoc_url=None)
    log.info(
        "model %s (%s, track %s) loaded; explainer provider %s",
        model.version,
        model.artefact["experiment"],
        model.artefact["generator"]["track"],
        ai.provider,
    )

    async def body_of(request: Request) -> tuple[dict | None, JSONResponse | None]:
        try:
            body = await request.json()
        except ValueError:
            return None, problem(400, "request body is not valid JSON")
        if not isinstance(body, dict):
            return None, problem(422, "request body must be a JSON object")
        return body, None

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "model_version": model.version}

    @app.get("/v1/model")
    def model_info() -> dict:
        a = model.artefact
        return {
            "name": a["name"],
            "model_version": a["model_version"],
            "schema_version": a["schema_version"],
            "experiment": a["experiment"],
            "trained_by_track": a["generator"]["track"],
            "high_risk_threshold": a["high_risk_threshold"],
            "base_rate": a["base_rate"],
            "training": a["training"],
            "test_metrics": a["test_metrics"],
            "features": [
                {
                    "name": f,
                    "type": model.specs[f].type,
                    "min": model.specs[f].min,
                    "max": model.specs[f].max,
                    "display": model.specs[f].display,
                    "unit": model.specs[f].unit,
                    "coefficient": a["coefficients"][f],
                    "training_mean": a["feature_means"][f],
                }
                for f in model.features
            ],
            "explainer": {"provider": ai.provider},
        }

    @app.post("/v1/predict")
    async def predict(request: Request):
        body, error = await body_of(request)
        if error:
            return error
        customers = body.get("customers")
        if not isinstance(customers, list) or not customers:
            return problem(422, "customers must be a non-empty list", [{"field": "customers", "problem": "required"}])
        if len(customers) > MAX_BATCH:
            return problem(413, f"at most {MAX_BATCH} customers per request")
        errors = []
        for i, c in enumerate(customers):
            if not isinstance(c, dict):
                errors.append({"field": f"customers[{i}]", "problem": "must be an object"})
                continue
            cid = c.get("customer_id")
            if cid is not None and (not isinstance(cid, str) or len(cid) > 64):
                errors.append({"field": f"customers[{i}].customer_id", "problem": "must be a string of <= 64"})
            errors += model.validate_row(c.get("features"), f"customers[{i}].features")
        if errors:
            return problem(422, "invalid customers", errors)
        out = []
        for c in customers:
            row = c["features"]
            p = model.score(row)
            out.append(
                {
                    "customer_id": c.get("customer_id"),
                    "churn_probability": round(p, 6),
                    "risk_band": model.risk_band(p),
                    "top_reasons": [
                        {"feature": r["feature"], "contribution": round(r["contribution"], 6)}
                        for r in model.contributions(row)[:3]
                    ],
                }
            )
        return {"predictions": out}

    @app.post("/v1/explain")
    async def explain_one(request: Request):
        body, error = await body_of(request)
        if error:
            return error
        errors = model.validate_row(body.get("features"), "features")
        if errors:
            return problem(422, "invalid features", errors)
        row = body["features"]
        p = model.score(row)
        note = explain(model, row, ai)
        if note.fallback:
            log.warning("explainer fell back to the template: %s", note.reason)
        return {"churn_probability": round(p, 6), "risk_band": model.risk_band(p), "explanation": note.to_dict()}

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC / "index.html", media_type="text/html")

    return app
