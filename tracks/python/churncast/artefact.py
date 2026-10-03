"""M5 · The model artefact (out/model.json): language-neutral, so the API can serve a model trained by any track.
Schema: contract/model.schema.json. Explanations are exact for a linear model: the contribution of feature j is
beta_j * (x_j - mean_j) on the log-odds scale (the training mean is the baseline)."""

from __future__ import annotations

import math

SCHEMA_VERSION = "1.1"  # 1.1 adds monitoring_reference and lineage (additive)


def build_artefact(
    fit: dict,
    experiment: str,
    features: list[str],
    means: dict,
    threshold: float,
    base_rate: float,
    training: dict,
    test_metrics: dict,
    version: str,
    track: str,
    monitoring_reference: dict | None = None,
    lineage: dict | None = None,
) -> dict:
    extra = {}
    if monitoring_reference is not None:
        extra["monitoring_reference"] = monitoring_reference
    if lineage is not None:
        extra["lineage"] = lineage
    return {
        "schema_version": SCHEMA_VERSION,
        "name": "churncast",
        "model_version": version,
        "kind": "logistic_regression",
        "target": "churned_next_month",
        "experiment": experiment,
        "features": features,
        "intercept": fit["intercept"],
        "coefficients": {f: fit["coefficients"][f] for f in features},
        "feature_means": {f: means[f] for f in features},
        "high_risk_threshold": threshold,
        "base_rate": base_rate,
        "training": training,
        "test_metrics": test_metrics,
        **extra,
        "generator": {"track": track, "version": version},
    }


def score(artefact: dict, row: dict) -> float:
    eta = artefact["intercept"] + sum(b * float(row[f]) for f, b in artefact["coefficients"].items())
    return 1.0 / (1.0 + math.exp(-eta))


def contributions(artefact: dict, row: dict) -> list[dict]:
    """Per-feature log-odds contributions, largest absolute first (ties: contract order)."""
    out = []
    for f, b in artefact["coefficients"].items():
        c = b * (float(row[f]) - artefact["feature_means"][f])
        out.append({"feature": f, "value": float(row[f]), "contribution": c})
    return sorted(out, key=lambda r: -abs(r["contribution"]))
