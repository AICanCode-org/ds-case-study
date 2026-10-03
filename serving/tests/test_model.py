import math

import pytest

from churncast_api.app import default_paths
from churncast_api.model import ArtefactError, load_model
from tests.conftest import REPO


def test_the_shipped_model_loads(model):
    assert model.version == "1.1.0" and model.artefact["lineage"]["parent_model_version"] == "1.0.0"
    assert model.features == model.artefact["features"]
    assert set(model.specs) >= set(model.features)


def test_score_and_contributions_agree(model, row):
    p = model.score(row)
    at_mean = model.artefact["intercept"] + sum(
        b * model.artefact["feature_means"][f] for f, b in model.artefact["coefficients"].items()
    )
    total = sum(c["contribution"] for c in model.contributions(row))
    assert math.isclose(math.log(p / (1 - p)), at_mean + total, abs_tol=1e-9)
    sizes = [abs(c["contribution"]) for c in model.contributions(row)]
    assert sizes == sorted(sizes, reverse=True)


def test_every_track_artefact_scores_the_same(model, row):
    """The Python, SQL and R tracks write the same model.json (parity), so any of them can be served."""
    p = default_paths()
    for track in ("python", "sql", "r"):
        path = REPO / "tracks" / track / "out" / "model.json"
        if not path.exists():
            pytest.skip(f"run `make run` in tracks/{track} first")
        other = load_model(path, p["contract"], p["schema"])
        assert math.isclose(other.score(row), model.score(row), rel_tol=1e-9)


def test_validation_lists_every_problem(model, row):
    bad = {**row, "tenure_months": -1, "is_new": 0.5, "meals_last_month": "nine", "colour": "red"}
    del bad["open_tickets"]
    problems = {p["field"].split(".")[-1]: p["problem"] for p in model.validate_row(bad, "x")}
    assert problems == {
        "colour": "unknown feature",
        "tenure_months": "must be between 0 and 240",
        "is_new": "must be 0 or 1",
        "meals_last_month": "must be a finite number",
        "open_tickets": "missing",
    }
    assert model.validate_row([1, 2], "x") == [{"field": "x", "problem": "must be an object of feature values"}]
    assert model.validate_row({**row, "tickets_90d": 1.5}, "x")[0]["problem"] == "must be a whole number"
    assert model.validate_row({**row, "late_rate_3m": float("nan")}, "x")[0]["problem"] == "must be a finite number"
    assert model.validate_row({**row, "is_new": True}, "x")[0]["problem"] == "must be a finite number"


def test_a_broken_artefact_is_refused(artefact_copy):
    p = default_paths()
    with pytest.raises(ArtefactError, match="schema"):
        load_model(artefact_copy(lambda a: a.pop("intercept")), p["contract"], p["schema"])
    with pytest.raises(ArtefactError, match="unsupported"):
        load_model(artefact_copy(lambda a: a.update(schema_version="2.0")), p["contract"], p["schema"])
    with pytest.raises(ArtefactError, match="contract"):
        load_model(artefact_copy(lambda a: a["features"].append("shoe_size")), p["contract"], p["schema"])
    with pytest.raises(ArtefactError, match="cannot read"):
        load_model(REPO / "nope.json", p["contract"], p["schema"])


def test_a_newer_minor_schema_still_loads(artefact_copy):
    """Forward compatibility: 1.x adds optional fields only, so this server serves a 1.9 artefact unchanged."""
    p = default_paths()
    m = load_model(
        artefact_copy(lambda a: a.update(schema_version="1.9", extra={"new": True})), p["contract"], p["schema"]
    )
    assert m.artefact["schema_version"] == "1.9"
