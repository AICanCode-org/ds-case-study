import numpy as np
import pandas as pd
import pytest

from churncast.model import fit_logistic, fit_prior, fit_rule, predict_logistic, predict_prior, predict_rule, rule_score
from tests.conftest import CASES

RULES = [{"feature": "a", "op": ">=", "value": 2}, {"feature": "b", "op": "<=", "value": 0}]


def test_logistic_regression_matches_the_shared_case():
    case = CASES["logistic"]
    x = pd.DataFrame({"x1": case["x1"], "x2": case["x2"]})
    fit = fit_logistic(x, pd.Series(case["y"]))
    assert fit["intercept"] == pytest.approx(case["intercept"], abs=1e-6)
    for name, b in case["coefficients"].items():
        assert fit["coefficients"][name] == pytest.approx(b, abs=1e-6)


def test_training_is_deterministic():
    case = CASES["logistic"]
    x = pd.DataFrame({"x1": case["x1"], "x2": case["x2"]})
    assert fit_logistic(x, pd.Series(case["y"])) == fit_logistic(x, pd.Series(case["y"]))


def test_predictions_are_probabilities():
    fit = {"intercept": 0.0, "coefficients": {"x": 1.0}}
    p = predict_logistic(fit, pd.DataFrame({"x": [-50.0, 0.0, 50.0]}))
    assert p[1] == 0.5 and 0 < p[0] < 1e-20 and p[2] == pytest.approx(1.0)


def test_rule_score_counts_flags():
    x = pd.DataFrame({"a": [0, 2, 5], "b": [1, 0, -1]})
    assert list(rule_score(x, RULES)) == [0, 2, 2]


def test_rule_baseline_is_a_lookup_of_training_rates():
    x = pd.DataFrame({"a": [0, 0, 3, 3], "b": [1, 1, 1, 0]})
    fit = fit_rule(x, pd.Series([0, 1, 1, 1]), RULES)
    assert fit["rates"] == {0: 0.5, 1: 1.0, 2: 1.0}
    unseen = fit_rule(x.iloc[:2], pd.Series([0, 1]), RULES)
    assert list(predict_rule(unseen, x, RULES)) == [0.5, 0.5, 0.5, 0.5]


def test_prior():
    fit = fit_prior(pd.Series([0, 0, 0, 1]))
    assert np.all(predict_prior(fit, pd.DataFrame({"x": [1, 2]})) == 0.25)
