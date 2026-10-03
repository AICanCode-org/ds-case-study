import math

import pytest

from churncast.artefact import SCHEMA_VERSION, build_artefact, contributions, score

FIT = {"intercept": -2.0, "coefficients": {"a": 0.5, "b": -1.0}}


def artefact():
    return build_artefact(
        FIT, "E2", ["a", "b"], {"a": 1.0, "b": 0.5}, 0.3, 0.1, {"export": "2026-05"}, {"auc": 0.8}, "1.0.0", "python"
    )


def test_artefact_shape():
    a = artefact()
    assert a["schema_version"] == SCHEMA_VERSION == "1.1"
    assert "monitoring_reference" not in a and "lineage" not in a  # optional: only when given
    assert list(a["coefficients"]) == a["features"] == ["a", "b"]
    assert a["generator"] == {"track": "python", "version": "1.0.0"}


def test_score_is_the_logistic_of_the_linear_predictor():
    assert score(artefact(), {"a": 2, "b": 1}) == pytest.approx(1 / (1 + math.exp(-(-2 + 1 - 1))))


def test_contributions_add_up_and_are_sorted():
    a = artefact()
    row = {"a": 3.0, "b": 0.0}
    c = contributions(a, row)
    assert [r["feature"] for r in c] == ["a", "b"]  # |0.5*2| = 1.0 > |-1*-0.5| = 0.5
    at_mean = a["intercept"] + sum(b * a["feature_means"][f] for f, b in a["coefficients"].items())
    eta = math.log(score(a, row) / (1 - score(a, row)))
    assert sum(r["contribution"] for r in c) == pytest.approx(eta - at_mean)


def test_monitoring_reference_and_lineage_are_additive():
    a = build_artefact(
        FIT,
        "E2",
        ["a", "b"],
        {"a": 1.0, "b": 0.5},
        0.3,
        0.1,
        {},
        {},
        "1.1.0",
        "python",
        {"bins": 10},
        {"parent_model_version": "1.0.0"},
    )
    assert a["monitoring_reference"] == {"bins": 10} and a["lineage"] == {"parent_model_version": "1.0.0"}
    assert list(a)[-1] == "generator"
