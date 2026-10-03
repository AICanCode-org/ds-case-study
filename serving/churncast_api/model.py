"""Load a model artefact, validate request rows against the contract, score and explain.

The artefact is language-neutral (contract/model.schema.json), so the same code serves a model trained by the
Python, SQL or R track. Scoring is the logistic of the linear predictor; the explanation of feature j is
beta_j * (x_j - mean_j) on the log-odds scale: exact for a linear model, no sampling, no SHAP library needed.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

SUPPORTED_MAJOR = "1"  # minor schema versions only add optional fields: a 1.0 server can serve any 1.x artefact


class ArtefactError(Exception):
    """The model file cannot be served."""


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    type: str
    min: float
    max: float
    display: str
    unit: str


@dataclass
class Model:
    artefact: dict
    specs: dict[str, FeatureSpec]

    @property
    def features(self) -> list[str]:
        return self.artefact["features"]

    @property
    def version(self) -> str:
        return self.artefact["model_version"]

    def validate_row(self, row: object, where: str) -> list[dict]:
        """Every problem of one request row (an empty list when the row is fine)."""
        if not isinstance(row, dict):
            return [{"field": where, "problem": "must be an object of feature values"}]
        problems = []
        for name in sorted(set(row) - set(self.features)):
            problems.append({"field": f"{where}.{name}", "problem": "unknown feature"})
        for name in self.features:
            spec = self.specs[name]
            field = f"{where}.{name}"
            if name not in row:
                problems.append({"field": field, "problem": "missing"})
                continue
            v = row[name]
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                problems.append({"field": field, "problem": "must be a finite number"})
            elif not spec.min <= v <= spec.max:
                problems.append({"field": field, "problem": f"must be between {spec.min:g} and {spec.max:g}"})
            elif spec.type == "binary" and v not in (0, 1):
                problems.append({"field": field, "problem": "must be 0 or 1"})
            elif spec.type == "int" and v != int(v):
                problems.append({"field": field, "problem": "must be a whole number"})
        return problems

    def score(self, row: dict) -> float:
        a = self.artefact
        eta = a["intercept"] + sum(b * float(row[f]) for f, b in a["coefficients"].items())
        return 1.0 / (1.0 + math.exp(-eta))

    def contributions(self, row: dict) -> list[dict]:
        """Per-feature log-odds contributions, largest absolute first (ties: model feature order)."""
        a = self.artefact
        out = [
            {
                "feature": f,
                "value": float(row[f]),
                "mean": a["feature_means"][f],
                "contribution": b * (float(row[f]) - a["feature_means"][f]),
            }
            for f, b in a["coefficients"].items()
        ]
        return sorted(out, key=lambda r: -abs(r["contribution"]))

    def risk_band(self, p: float) -> str:
        return "high" if p >= self.artefact["high_risk_threshold"] else "normal"


def load_model(model_path: str | Path, contract_path: str | Path, schema_path: str | Path) -> Model:
    try:
        artefact = json.loads(Path(model_path).read_text(encoding="utf-8"))
        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        contract = yaml.safe_load(Path(contract_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ArtefactError(f"cannot read the model, schema or contract: {exc}") from exc
    version = str(artefact.get("schema_version", "")) if isinstance(artefact, dict) else ""
    if version.split(".")[0] != SUPPORTED_MAJOR:
        raise ArtefactError(f"unsupported artefact schema {version!r} (this server reads {SUPPORTED_MAJOR}.x)")
    errors = list(Draft202012Validator(schema).iter_errors(artefact))
    if errors:
        raise ArtefactError(f"model file does not match the schema: {errors[0].message}")
    specs = {
        f["name"]: FeatureSpec(f["name"], f["type"], float(f["min"]), float(f["max"]), f["display"], f["unit"])
        for f in contract["features"]
    }
    unknown = [f for f in artefact["features"] if f not in specs]
    if unknown or set(artefact["coefficients"]) != set(artefact["features"]):
        raise ArtefactError(f"model features do not match the contract: {unknown or 'coefficients'}")
    return Model(artefact, specs)
