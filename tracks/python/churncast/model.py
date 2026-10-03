"""M4 · Baselines and the logistic regression (contract/feature-spec.md §5).

Unpenalised logistic regression (C = inf) with the Newton-Cholesky solver: the maximum-likelihood fit, the same
numbers R's glm() finds, so the tracks can be compared. No scaling is needed to fit it, and the coefficients stay
in the units of the features (per month, per meal, per ticket), which is what the explanations use.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


def fit_logistic(x: pd.DataFrame, y: pd.Series) -> dict:
    model = LogisticRegression(C=math.inf, solver="newton-cholesky", max_iter=100, tol=1e-12)
    model.fit(x.to_numpy(dtype=float), y.to_numpy(dtype=int))
    return {
        "intercept": float(model.intercept_[0]),
        "coefficients": {name: float(b) for name, b in zip(x.columns, model.coef_[0], strict=True)},
    }


def linear_predictor(fit: dict, x: pd.DataFrame) -> np.ndarray:
    """intercept + b1 * x1 + b2 * x2 + ..., added up in feature order, one element at a time. Not a matrix product:
    BLAS kernels may add up rows in different orders (blocks, FMA), so two identical rows could score a last bit
    apart and break a tie. This way every track (and every CPU) gets bit-identical scores."""
    eta = np.full(len(x), float(fit["intercept"]))
    for name, beta in fit["coefficients"].items():
        eta = eta + beta * x[name].to_numpy(dtype=float)
    return eta


def predict_logistic(fit: dict, x: pd.DataFrame) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-linear_predictor(fit, x)))


def rule_score(x: pd.DataFrame, rules: list[dict]) -> np.ndarray:
    """B1: one point per risk flag of the contract's rule_baseline."""
    score = np.zeros(len(x), dtype=int)
    for r in rules:
        v = x[r["feature"]].to_numpy(dtype=float)
        score += (v >= r["value"]) if r["op"] == ">=" else (v <= r["value"])
    return score


def fit_rule(x: pd.DataFrame, y: pd.Series, rules: list[dict]) -> dict:
    """The churn rate of the training rows for each flag count (a lookup table), the overall rate for unseen counts."""
    score = rule_score(x, rules)
    table = pd.Series(y.to_numpy(dtype=float)).groupby(score).mean()
    return {"rates": {int(k): float(v) for k, v in table.items()}, "default": float(y.mean())}


def predict_rule(fit: dict, x: pd.DataFrame, rules: list[dict]) -> np.ndarray:
    return np.array([fit["rates"].get(int(s), fit["default"]) for s in rule_score(x, rules)], dtype=float)


def fit_prior(y: pd.Series) -> dict:
    return {"rate": float(y.mean())}


def predict_prior(fit: dict, x: pd.DataFrame) -> np.ndarray:
    return np.full(len(x), fit["rate"], dtype=float)
