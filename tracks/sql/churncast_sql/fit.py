"""M4 · The one step SQL cannot do: fit the logistic regression.

Unpenalised (C = inf) with the Newton-Cholesky solver, exactly as the Python track, so the coefficients agree. The
fit returns plain numbers; scoring happens back in SQL (runner.score_sql builds the linear predictor)."""

from __future__ import annotations

import math

import numpy as np
from sklearn.linear_model import LogisticRegression


def fit_logistic(x: np.ndarray, y: np.ndarray, names: list[str]) -> dict:
    model = LogisticRegression(C=math.inf, solver="newton-cholesky", max_iter=100, tol=1e-12)
    model.fit(np.asarray(x, dtype=float), np.asarray(y, dtype=int))
    return {
        "intercept": float(model.intercept_[0]),
        "coefficients": {n: float(b) for n, b in zip(names, model.coef_[0], strict=True)},
    }
