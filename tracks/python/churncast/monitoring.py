"""M7 · Monitoring and retraining (contract/feature-spec.md §9), the v1.1 work after the model went live.

Monitoring: is the deployed model still fit for use?
- drift: the population stability index (PSI) of every feature and of the deployed score, each post-deployment
  snapshot against the training rows. Bins = decile edges (type-7 quantiles) of the training values, duplicate edges
  dropped; bin of x = number of edges strictly below x; PSI = sum (a - e) * ln(a / e) with empty bins at psi_floor.
- realised performance: on every labelled post-deployment month, AUC, Brier, ECE and mean predicted vs observed.

Retraining: a challenger refitted on all labelled pre-deployment snapshots, its intercept recalibrated on the most
recent labelled month (one Newton step at a time: the offset d with sum(sigmoid(eta + d)) = sum(y)), then champion
and challenger are compared on the holdout month neither has seen. The challenger is promoted only if every check of
the contract's retraining gate passes.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .evaluate import auc, brier, calibration, contacted, quantile7, score_metrics
from .model import fit_logistic, linear_predictor, predict_logistic

POST_DEPLOYMENT = ("recent", "holdout", "score")


def psi_edges(values, bins: int) -> list[float]:
    v = np.asarray(values, dtype=float)
    edges = [quantile7(v, k / bins) for k in range(1, bins)]
    return sorted(set(edges))


def bin_shares(values, edges: list[float]) -> list[float]:
    v = np.asarray(values, dtype=float)
    idx = np.searchsorted(np.asarray(edges), v, side="left")  # number of edges strictly below each value
    counts = np.bincount(idx, minlength=len(edges) + 1)
    return [float(c / len(v)) for c in counts]


def psi(reference: list[float], actual: list[float], floor: float) -> float:
    total = 0.0
    for e, a in zip(reference, actual, strict=True):
        e, a = max(e, floor), max(a, floor)
        total += (a - e) * math.log(a / e)
    return total


def reference_profile(rows: pd.DataFrame, features: list[str], scores, bins: int) -> dict:
    """What a later monitoring run compares against: decile edges and shares of each feature and of the score."""
    out = {"bins": bins, "rows": len(rows), "features": {}}
    for f in features:
        edges = psi_edges(rows[f], bins)
        out["features"][f] = {"edges": edges, "shares": bin_shares(rows[f], edges)}
    edges = psi_edges(scores, bins)
    out["score"] = {"edges": edges, "shares": bin_shares(scores, edges)}
    return out


def psi_status(value: float, mon: dict) -> str:
    if value >= mon["psi_drift"]:
        return "drift"
    return "watch" if value >= mon["psi_watch"] else "stable"


def recall_gap(frame: pd.DataFrame, y, p, ev: dict, missing: str) -> float:
    """Fairness on one evaluation month: max - min recall of the top-k call list across the fairness groups."""
    y = np.asarray(y, dtype=int)
    c = contacted(frame, p, ev["top_percent"])
    f = ev["fairness"]
    values = frame[f["dimension"]].astype(str).to_numpy()
    recalls = []
    for v in sorted(set(values)):
        m = values == v
        if v != missing and int(y[m].sum()) >= f["min_churners"]:
            recalls.append(float((c[m] & (y[m] == 1)).sum() / y[m].sum()))
    return max(recalls) - min(recalls)


def performance(y, p) -> dict:
    cal = calibration(y, p, 10)
    return {
        "auc": auc(y, p),
        "brier": brier(y, p),
        "ece": cal["ece"],
        "mean_pred": cal["mean_pred"],
        "observed_rate": cal["observed_rate"],
    }


def monitor(features: pd.DataFrame, deployed: dict, contract: dict) -> dict:
    mon = contract["monitoring"]
    names = deployed["features"]
    reference = features[features["split"] == "train"]
    ref = reference_profile(reference, names, predict_logistic(deployed, reference), mon["psi_bins"])
    drift, perf, alerts = [], [], []
    for snap, g in features[features["split"].isin(POST_DEPLOYMENT)].groupby("snapshot", sort=True):
        p = predict_logistic(deployed, g)
        per = {
            f: psi(ref["features"][f]["shares"], bin_shares(g[f], ref["features"][f]["edges"]), mon["psi_floor"])
            for f in names
        }
        score_psi = psi(ref["score"]["shares"], bin_shares(p, ref["score"]["edges"]), mon["psi_floor"])
        drift.append(
            {
                "snapshot": snap,
                "split": g["split"].iloc[0],
                "rows": len(g),
                "score_psi": score_psi,
                "score_status": psi_status(score_psi, mon),
                "feature_psi": per,
                "features_watch": [f for f in names if psi_status(per[f], mon) == "watch"],
                "features_drift": [f for f in names if psi_status(per[f], mon) == "drift"],
            }
        )
        for f in drift[-1]["features_drift"]:
            alerts.append(f"{snap}: {f} drifted (PSI {per[f]:.3f})")
        if g["churned"].notna().all():
            m = performance(g["churned"].astype(int), p)
            own = []
            if m["ece"] > mon["alert_max_ece"]:
                own.append(f"ECE {m['ece']:.3f} > {mon['alert_max_ece']}")
            if abs(m["mean_pred"] - m["observed_rate"]) > mon["alert_max_mean_gap"]:
                own.append(f"mean predicted {m['mean_pred']:.3f} vs observed {m['observed_rate']:.3f}")
            if m["auc"] < mon["alert_min_auc"]:
                own.append(f"AUC {m['auc']:.3f} < {mon['alert_min_auc']}")
            perf.append({"snapshot": snap, "split": g["split"].iloc[0], "rows": len(g), **m, "alerts": own})
            alerts += [f"{snap}: {a}" for a in own]
    return {
        "deployed_model": {
            "path": mon["deployed_model"],
            "model_version": deployed["model_version"],
            "trained_by_track": deployed["generator"]["track"],
        },
        "reference": {"split": "train", "rows": len(reference)},
        "drift": drift,
        "performance": perf,
        "alerts": alerts,
        "status": "retrain" if any(r["alerts"] for r in perf) else ("watch" if alerts else "ok"),
    }


def calibration_offset(eta, y) -> float:
    """The intercept shift d with sum(sigmoid(eta + d)) = sum(y): Newton's method in one dimension."""
    eta, y = np.asarray(eta, dtype=float), np.asarray(y, dtype=float)
    d = 0.0
    for _ in range(100):
        p = 1.0 / (1.0 + np.exp(-(eta + d)))
        step = float((p - y).sum() / (p * (1 - p)).sum())
        d -= step
        if abs(step) < 1e-13:
            break
    return d


def retrain(features: pd.DataFrame, deployed: dict, contract: dict) -> dict:
    rt, ev = contract["retraining"], contract["evaluation"]
    names = deployed["features"]
    refit = features[features["split"].isin(rt["refit_splits"])]
    calib = features[features["split"] == rt["calibrate_on"]]
    hold = features[features["split"] == rt["decide_on"]].reset_index(drop=True)
    fit = fit_logistic(refit[names], refit["churned"].astype(int))
    offset = calibration_offset(linear_predictor(fit, calib), calib["churned"].astype(int))
    challenger = {"intercept": fit["intercept"] + offset, "coefficients": fit["coefficients"]}
    y = hold["churned"].astype(int)
    missing = contract["cleaning"]["missing_label"]
    results = {}
    for who, model in (("champion", deployed), ("challenger", challenger)):
        p = predict_logistic(model, hold)
        results[who] = {
            **score_metrics(hold, y, p, ev),
            "mean_pred": float(np.mean(p)),
            "observed_rate": float(y.mean()),
            "recall_gap": recall_gap(hold, y, p, ev, missing),
        }
    ch, cc = results["champion"], results["challenger"]
    checks = [
        {
            "id": "auc_not_worse",
            "value": cc["auc"],
            "threshold": ch["auc"] - rt["max_auc_drop"],
            "passed": cc["auc"] >= ch["auc"] - rt["max_auc_drop"],
        },
        {"id": "brier_improves", "value": cc["brier"], "threshold": ch["brier"], "passed": cc["brier"] < ch["brier"]},
        {"id": "ece", "value": cc["ece"], "threshold": rt["max_ece"], "passed": cc["ece"] <= rt["max_ece"]},
        {
            "id": "recall_gap",
            "value": cc["recall_gap"],
            "threshold": rt["max_recall_gap"],
            "passed": cc["recall_gap"] <= rt["max_recall_gap"],
        },
    ]
    for c in checks:
        c["passed"] = bool(c["passed"])
    passed = all(c["passed"] for c in checks)
    calib_p = predict_logistic(challenger, calib)
    return {
        "fit": challenger,
        "refit_rows": refit,
        "calibration_rows": calib,
        "calibration_scores": calib_p,
        "section": {
            "challenger": {
                "features": names,
                "refit_snapshots": sorted(refit["snapshot"].unique().tolist()),
                "refit_rows": len(refit),
                "calibration_snapshot": calib["snapshot"].iloc[0],
                "calibration_offset": offset,
                "intercept": challenger["intercept"],
                "coefficients": challenger["coefficients"],
            },
            "holdout": {"snapshot": hold["snapshot"].iloc[0], "rows": len(hold), "churn_rate": float(y.mean())},
            "champion_holdout": ch,
            "challenger_holdout": cc,
            "gate": {"checks": checks, "passed": passed},
            "decision": "promote" if passed else "keep",
        },
    }
