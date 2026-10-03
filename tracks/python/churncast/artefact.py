"""M5 · The model artefact (out/model.json): language-neutral, so the API can serve a model trained by any track.
Schema: contract/model.schema.json. Explanations are exact for a linear model: the contribution of feature j is
beta_j * (x_j - mean_j) on the log-odds scale (the training mean is the baseline)."""

from __future__ import annotations

SCHEMA_VERSION = "1.0"


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
) -> dict:
    # TODO(M5) build_artefact: model.json exactly as contract/model.schema.json describes: any track's artefact
    # must be servable by the API. Spec: contract/feature-spec.md §7 and contract/model.schema.json; tests:
    # artefact.
    raise NotImplementedError("TODO(M5) build_artefact: see the comment above")


def score(artefact: dict, row: dict) -> float:
    # TODO(M5) score: the probability for one customer (a dict of feature values). Spec:
    # contract/feature-spec.md §7 and contract/model.schema.json; tests: artefact.
    raise NotImplementedError("TODO(M5) score: see the comment above")


def contributions(artefact: dict, row: dict) -> list[dict]:
    """Per-feature log-odds contributions, largest absolute first (ties: contract order)."""
    # TODO(M5) contributions: beta_j * (x_j - training mean_j) on the log-odds scale, largest absolute first.
    # Spec: contract/feature-spec.md §7 and contract/model.schema.json; tests: artefact.
    raise NotImplementedError("TODO(M5) contributions: see the comment above")
