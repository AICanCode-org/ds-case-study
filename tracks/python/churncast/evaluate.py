"""M4-M5 · Evaluation (contract/feature-spec.md §6): metrics written out by hand so every track computes exactly the
same number, plus calibration, the retention-capacity view (top 10 % per month), slices, fairness, leakage and gate."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

EPS = 1e-15


def auc(y, p) -> float | None:
    """Area under the ROC curve = P(score of a churner > score of a stayer), ties count 1/2 (average ranks)."""
    # TODO(M4) auc: P(score of a churner > score of a stayer), ties count 1/2 (average ranks); null with one
    # class only. Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
    raise NotImplementedError("TODO(M4) auc: see the comment above")


def average_precision(y, p) -> float | None:
    """sum over distinct thresholds (high to low) of (recall_k - recall_k-1) * precision_k."""
    # TODO(M4) average_precision: sum over distinct scores, high to low, of (recall_k - recall_k-1) *
    # precision_k. Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
    raise NotImplementedError("TODO(M4) average_precision: see the comment above")


def brier(y, p) -> float:
    # TODO(M4) brier: mean squared error of the probabilities. Spec: contract/feature-spec.md §6 (+
    # contract/fixtures/metric-cases.json); tests: metrics.
    raise NotImplementedError("TODO(M4) brier: see the comment above")


def log_loss(y, p) -> float:
    # TODO(M4) log_loss: clip p to [1e-15, 1 - 1e-15] first. Spec: contract/feature-spec.md §6 (+
    # contract/fixtures/metric-cases.json); tests: metrics.
    raise NotImplementedError("TODO(M4) log_loss: see the comment above")


def calibration(y, p, bins: int) -> dict:
    # TODO(M4) calibration: 10 equal-width bins ([k/10, (k+1)/10), p = 1 in the last); ECE = sum n_b / n * |mean
    # p - observed|. Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
    raise NotImplementedError("TODO(M4) calibration: see the comment above")


def top_k(n: int, percent: int) -> int:
    return (n * percent + 99) // 100  # ceil(n * percent / 100) in integers: no floating-point surprise


def contacted(frame: pd.DataFrame, p, percent: int) -> np.ndarray:
    """True for the top `percent` % of each snapshot by risk (ties: lower customer_id first)."""
    # TODO(M4) contacted: the top k of EACH snapshot by risk; ties: the lower customer_id first. Spec:
    # contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
    raise NotImplementedError("TODO(M4) contacted: see the comment above")


def capacity_metrics(frame: pd.DataFrame, y, p, ev: dict) -> dict:
    # TODO(M4) capacity_metrics: precision, recall and lift of the call list, and the net value per month
    # (contract's cost, save rate and value months). Spec: contract/feature-spec.md §6 (+
    # contract/fixtures/metric-cases.json); tests: metrics.
    raise NotImplementedError("TODO(M4) capacity_metrics: see the comment above")


def score_metrics(frame: pd.DataFrame, y, p, ev: dict) -> dict:
    # TODO(M4) score_metrics: every test metric of one experiment: AUC, AP, Brier, log loss, ECE + the capacity
    # metrics. Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
    raise NotImplementedError("TODO(M4) score_metrics: see the comment above")


def slices(frame: pd.DataFrame, y, p, ev: dict) -> dict:
    # TODO(M4) slices: per slice value: rows, churners, mean prediction, AUC only with enough rows and churners,
    # recall of the call list. Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests:
    # metrics.
    raise NotImplementedError("TODO(M4) slices: see the comment above")


def fairness(slice_rows: dict, ev: dict, missing: str) -> dict:
    # TODO(M4) fairness: recall gap of the call list across age bands with >= min_churners (never 'unknown').
    # Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
    raise NotImplementedError("TODO(M4) fairness: see the comment above")


def leakage_scan(train: pd.DataFrame, features: list[str], probe: np.ndarray, limit: float) -> dict:
    """Single-feature AUC (folded to >= 0.5) of every model feature on the training rows, and of the leaky probe."""
    # TODO(M4) leakage_scan: single-feature AUC (folded to >= 0.5) of every model feature on the training rows,
    # and of the cancellation_reason probe (it should look suspiciously good: that is why it is banned). Spec:
    # contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
    raise NotImplementedError("TODO(M4) leakage_scan: see the comment above")


def gate(test: dict, rule_test: dict, prior_test: dict, fair: dict, leak: dict, g: dict) -> dict:
    # TODO(M4) gate: the six release checks of the contract, in order. Spec: contract/feature-spec.md §6 (+
    # contract/fixtures/metric-cases.json); tests: metrics.
    raise NotImplementedError("TODO(M4) gate: see the comment above")


def quantile7(values, q: float) -> float:
    """Type-7 quantile (numpy's and R's default): linear interpolation between order statistics."""
    v = np.sort(np.asarray(values, dtype=float))
    h = (len(v) - 1) * q
    lo = math.floor(h)
    return float(v[lo] + (h - lo) * (v[min(lo + 1, len(v) - 1)] - v[lo]))
