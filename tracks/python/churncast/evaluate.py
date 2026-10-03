"""M4-M5 · Evaluation (contract/feature-spec.md §6): metrics written out by hand so every track computes exactly the
same number, plus calibration, the retention-capacity view (top 10 % per month), slices, fairness, leakage and gate."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

EPS = 1e-15


def auc(y, p) -> float | None:
    """Area under the ROC curve = P(score of a churner > score of a stayer), ties count 1/2 (average ranks)."""
    y, p = np.asarray(y, dtype=int), np.asarray(p, dtype=float)
    n_pos, n_neg = int(y.sum()), int(len(y) - y.sum())
    if n_pos == 0 or n_neg == 0:
        return None
    ranks = pd.Series(p).rank(method="average").to_numpy()
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def average_precision(y, p) -> float | None:
    """sum over distinct thresholds (high to low) of (recall_k - recall_k-1) * precision_k."""
    y, p = np.asarray(y, dtype=int), np.asarray(p, dtype=float)
    n_pos = int(y.sum())
    if n_pos == 0:
        return None
    df = pd.DataFrame({"p": p, "y": y}).groupby("p", sort=True)["y"].agg(["sum", "count"]).iloc[::-1]
    tp, n = df["sum"].cumsum().to_numpy(), df["count"].cumsum().to_numpy()
    recall = tp / n_pos
    precision = tp / n
    return float(np.sum(np.diff(np.concatenate([[0.0], recall])) * precision))


def brier(y, p) -> float:
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    return float(np.mean((p - y) ** 2))


def log_loss(y, p) -> float:
    y, p = np.asarray(y, dtype=float), np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def calibration(y, p, bins: int) -> dict:
    y, p = np.asarray(y, dtype=float), np.asarray(p, dtype=float)
    b = np.minimum(np.floor(p * bins).astype(int), bins - 1)
    rows, ece = [], 0.0
    for k in range(bins):
        m = b == k
        n = int(m.sum())
        mean_pred = float(p[m].mean()) if n else None
        observed = float(y[m].mean()) if n else None
        if n:
            ece += n / len(p) * abs(mean_pred - observed)
        rows.append(
            {"bin": k, "lower": k / bins, "upper": (k + 1) / bins, "n": n, "mean_pred": mean_pred, "observed": observed}
        )
    return {"bins": rows, "ece": float(ece), "mean_pred": float(p.mean()), "observed_rate": float(y.mean())}


def top_k(n: int, percent: int) -> int:
    return (n * percent + 99) // 100  # ceil(n * percent / 100) in integers: no floating-point surprise


def contacted(frame: pd.DataFrame, p, percent: int) -> np.ndarray:
    """True for the top `percent` % of each snapshot by risk (ties: lower customer_id first)."""
    df = pd.DataFrame(
        {
            "snapshot": frame["snapshot"].to_numpy(),
            "customer_id": frame["customer_id"].to_numpy(),
            "p": np.asarray(p, dtype=float),
            "i": np.arange(len(frame)),
        }
    )
    flag = np.zeros(len(frame), dtype=bool)
    for _, g in df.groupby("snapshot", sort=True):
        g = g.sort_values(["p", "customer_id"], ascending=[False, True])
        flag[g["i"].to_numpy()[: top_k(len(g), percent)]] = True
    return flag


def capacity_metrics(frame: pd.DataFrame, y, p, ev: dict) -> dict:
    y = np.asarray(y, dtype=int)
    c = contacted(frame, p, ev["top_percent"])
    hits = int(y[c].sum())
    precision = hits / int(c.sum())
    recall = hits / int(y.sum())
    saved = (y[c] * frame["price_inr"].to_numpy(dtype=float)[c]).sum() * ev["save_rate"] * ev["value_months"]
    months = frame["snapshot"].nunique()
    return {
        "contacted": int(c.sum()),
        "churners_reached": hits,
        "precision_at_top": precision,
        "recall_at_top": recall,
        "lift_at_top": precision / float(y.mean()),
        "net_value_inr_per_month": float((saved - ev["offer_cost_inr"] * int(c.sum())) / months),
    }


def score_metrics(frame: pd.DataFrame, y, p, ev: dict) -> dict:
    return {
        "auc": auc(y, p),
        "average_precision": average_precision(y, p),
        "brier": brier(y, p),
        "log_loss": log_loss(y, p),
        "ece": calibration(y, p, ev["calibration_bins"])["ece"],
        **capacity_metrics(frame, y, p, ev),
    }


def slices(frame: pd.DataFrame, y, p, ev: dict) -> dict:
    y, p = np.asarray(y, dtype=int), np.asarray(p, dtype=float)
    c = contacted(frame, p, ev["top_percent"])
    out = {}
    for dim in ev["slices"]:
        rows = []
        values = frame[dim].astype(str).to_numpy()
        for v in sorted(set(values)):
            m = values == v
            n, churners = int(m.sum()), int(y[m].sum())
            enough = (
                n >= ev["min_slice_rows_for_auc"] and min(churners, n - churners) >= ev["min_slice_churners_for_auc"]
            )
            rows.append(
                {
                    "value": v,
                    "n": n,
                    "churners": churners,
                    "churn_rate": churners / n,
                    "mean_pred": float(p[m].mean()),
                    "auc": auc(y[m], p[m]) if enough else None,
                    "contacted": int(c[m].sum()),
                    "flagged_rate": float(c[m].sum() / n),
                    "recall_at_top": float((c[m] & (y[m] == 1)).sum() / churners) if churners else None,
                }
            )
        out[dim] = rows
    return out


def fairness(slice_rows: dict, ev: dict, missing: str) -> dict:
    f = ev["fairness"]
    groups = [r for r in slice_rows[f["dimension"]] if r["value"] != missing and r["churners"] >= f["min_churners"]]
    recalls = [r["recall_at_top"] for r in groups]
    flagged = [r["flagged_rate"] for r in groups]
    gap = max(recalls) - min(recalls)
    return {
        "dimension": f["dimension"],
        "groups": [r["value"] for r in groups],
        "recall_gap": gap,
        "flagged_rate_ratio": min(flagged) / max(flagged) if max(flagged) > 0 else None,
        "max_recall_gap": f["max_recall_gap"],
        "passed": bool(gap <= f["max_recall_gap"]),
    }


def leakage_scan(train: pd.DataFrame, features: list[str], probe: np.ndarray, limit: float) -> dict:
    """Single-feature AUC (folded to >= 0.5) of every model feature on the training rows, and of the leaky probe."""
    y = train["churned"].to_numpy(dtype=int)
    per = {}
    for name in features:
        a = auc(y, train[name].to_numpy(dtype=float))
        per[name] = max(a, 1 - a)
    worst = max(features, key=lambda k: per[k])  # the first one in contract order on a tie
    pa = auc(y, probe)
    return {
        "feature_auc": per,
        "max_feature": worst,
        "max_feature_auc": per[worst],
        "limit": limit,
        "probe": "customers.cancellation_reason is filled",
        "probe_auc": max(pa, 1 - pa),
        "passed": bool(per[worst] < limit),
    }


def gate(test: dict, rule_test: dict, prior_test: dict, fair: dict, leak: dict, g: dict) -> dict:
    checks = [
        {
            "id": "test_auc",
            "value": test["auc"],
            "threshold": g["min_test_auc"],
            "passed": test["auc"] >= g["min_test_auc"],
        },
        {
            "id": "auc_uplift_over_rule",
            "value": test["auc"] - rule_test["auc"],
            "threshold": g["min_auc_uplift_over_rule"],
            "passed": test["auc"] - rule_test["auc"] >= g["min_auc_uplift_over_rule"],
        },
        {"id": "ece", "value": test["ece"], "threshold": g["max_ece"], "passed": test["ece"] <= g["max_ece"]},
        {
            "id": "brier_below_prior",
            "value": test["brier"],
            "threshold": prior_test["brier"],
            "passed": test["brier"] < prior_test["brier"],
        },
        {
            "id": "recall_gap",
            "value": fair["recall_gap"],
            "threshold": g["max_recall_gap"],
            "passed": fair["recall_gap"] <= g["max_recall_gap"],
        },
        {"id": "leakage_scan", "value": leak["max_feature_auc"], "threshold": leak["limit"], "passed": leak["passed"]},
    ]
    for c in checks:
        c["passed"] = bool(c["passed"])
    return {"checks": checks, "passed": all(c["passed"] for c in checks)}


def quantile7(values, q: float) -> float:
    """Type-7 quantile (numpy's and R's default): linear interpolation between order statistics."""
    v = np.sort(np.asarray(values, dtype=float))
    h = (len(v) - 1) * q
    lo = math.floor(h)
    return float(v[lo] + (h - lo) * (v[min(lo + 1, len(v) - 1)] - v[lo]))
