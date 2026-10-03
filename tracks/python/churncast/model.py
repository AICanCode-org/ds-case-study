"""M4 · Baselines and the logistic regression (contract/feature-spec.md §5).

Unpenalised logistic regression (C = inf) with the Newton-Cholesky solver: the maximum-likelihood fit, the same
numbers R's glm() finds, so the tracks can be compared. No scaling is needed to fit it, and the coefficients stay
in the units of the features (per month, per meal, per ticket), which is what the explanations use.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def fit_logistic(x: pd.DataFrame, y: pd.Series) -> dict:
    # TODO(M4) fit_logistic: unpenalised maximum-likelihood logistic regression (no regularisation: the contract
    # compares tracks to 1e-6, and every library's default penalty differs). Spec: contract/feature-spec.md §5;
    # tests: model.
    raise NotImplementedError("TODO(M4) fit_logistic: see the comment above")


def linear_predictor(fit: dict, x: pd.DataFrame) -> np.ndarray:
    """intercept + b1 * x1 + b2 * x2 + ..., added up in feature order, one element at a time. Not a matrix product:
    BLAS kernels may add up rows in different orders (blocks, FMA), so two identical rows could score a last bit
    apart and break a tie. This way every track (and every CPU) gets bit-identical scores."""
    # TODO(M4) linear_predictor: intercept + b1 * x1 + b2 * x2 + ... added feature by feature, NOT a matrix
    # product: BLAS kernels add rows in different orders, so two identical customers could score an ulp apart
    # and break a tie. Spec: contract/feature-spec.md §5; tests: model.
    raise NotImplementedError("TODO(M4) linear_predictor: see the comment above")


def predict_logistic(fit: dict, x: pd.DataFrame) -> np.ndarray:
    # TODO(M4) predict_logistic: the logistic of the linear predictor. Spec: contract/feature-spec.md §5; tests:
    # model.
    raise NotImplementedError("TODO(M4) predict_logistic: see the comment above")


def rule_score(x: pd.DataFrame, rules: list[dict]) -> np.ndarray:
    """B1: one point per risk flag of the contract's rule_baseline."""
    # TODO(M4) rule_score: B1: one point per risk flag of the contract's rule_baseline. Spec:
    # contract/feature-spec.md §5; tests: model.
    raise NotImplementedError("TODO(M4) rule_score: see the comment above")


def fit_rule(x: pd.DataFrame, y: pd.Series, rules: list[dict]) -> dict:
    """The churn rate of the training rows for each flag count (a lookup table), the overall rate for unseen counts."""
    # TODO(M4) fit_rule: the training churn rate for each flag count; the overall rate for a count never seen in
    # training. Spec: contract/feature-spec.md §5; tests: model.
    raise NotImplementedError("TODO(M4) fit_rule: see the comment above")


def predict_rule(fit: dict, x: pd.DataFrame, rules: list[dict]) -> np.ndarray:
    # TODO(M4) predict_rule: look up the rate of each row's flag count. Spec: contract/feature-spec.md §5;
    # tests: model.
    raise NotImplementedError("TODO(M4) predict_rule: see the comment above")


def fit_prior(y: pd.Series) -> dict:
    # TODO(M4) fit_prior: B0: the training churn rate. Spec: contract/feature-spec.md §5; tests: model.
    raise NotImplementedError("TODO(M4) fit_prior: see the comment above")


def predict_prior(fit: dict, x: pd.DataFrame) -> np.ndarray:
    # TODO(M4) predict_prior: everyone gets the training churn rate (AUC exactly 0.5). Spec:
    # contract/feature-spec.md §5; tests: model.
    raise NotImplementedError("TODO(M4) predict_prior: see the comment above")
