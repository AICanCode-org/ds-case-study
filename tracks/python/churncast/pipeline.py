"""M5 · The whole run: raw export -> checks -> features -> experiments -> champion -> evaluation -> artefacts.

out/features.csv     one row per customer and snapshot (the parity check compares it across tracks)
out/metrics.json     everything the model card, the tests and CI read (schema: contract/metrics.schema.json)
out/model.json       the champion, language-neutral (schema: contract/model.schema.json)
out/experiments.jsonl  the experiment log: one line per experiment
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__
from .artefact import build_artefact
from .checks import raise_on_errors, run_checks
from .clean import clean_tables, month_index
from .contract import feature_names, load_contract
from .evaluate import auc, brier, calibration, fairness, gate, leakage_scan, log_loss, quantile7, score_metrics, slices
from .features import build_features, snapshot_summary
from .load import load_export_meta, load_raw
from .model import fit_logistic, fit_prior, fit_rule, predict_logistic, predict_prior, predict_rule

TRACK = "python"


def experiment_features(exp: dict, contract: dict) -> list[str]:
    if exp["kind"] != "logistic":
        return []
    return feature_names(contract, core_only=exp["features"] == "core")


def fit_experiment(exp: dict, contract: dict, rows: pd.DataFrame) -> dict:
    y = rows["churned"].astype(int)
    if exp["kind"] == "prior":
        return fit_prior(y)
    if exp["kind"] == "rule":
        return fit_rule(rows, y, contract["rule_baseline"])
    return fit_logistic(rows[experiment_features(exp, contract)], y)


def predict_experiment(exp: dict, contract: dict, fit: dict, rows: pd.DataFrame) -> np.ndarray:
    if exp["kind"] == "prior":
        return predict_prior(fit, rows)
    if exp["kind"] == "rule":
        return predict_rule(fit, rows, contract["rule_baseline"])
    return predict_logistic(fit, rows)


def cross_validate(exp: dict, contract: dict, train: pd.DataFrame) -> dict:
    folds = []
    for k in range(contract["snapshots"]["folds"]):
        fit_rows, val = train[train["fold"] != k], train[train["fold"] == k]
        p = predict_experiment(exp, contract, fit_experiment(exp, contract, fit_rows), val)
        y = val["churned"].astype(int)
        folds.append({"fold": k, "rows": len(val), "auc": auc(y, p), "brier": brier(y, p), "log_loss": log_loss(y, p)})
    a = np.array([f["auc"] for f in folds])
    return {
        "auc_mean": float(a.mean()),
        "auc_sd": float(a.std(ddof=1)),
        "brier_mean": float(np.mean([f["brier"] for f in folds])),
        "log_loss_mean": float(np.mean([f["log_loss"] for f in folds])),
        "folds": folds,
    }


def choose_champion(experiments: list[dict], contract: dict) -> tuple[str, str]:
    logistic = [e for e in experiments if e["kind"] == "logistic"]
    simple, bigger = logistic[0], logistic[-1]
    gain = bigger["cv"]["auc_mean"] - simple["cv"]["auc_mean"]
    need = contract["champion"]["min_cv_auc_gain_for_complexity"]
    if gain >= need:
        return bigger["id"], f"{bigger['id']} beats {simple['id']} by {gain:.4f} mean CV AUC (>= {need})"
    return simple["id"], f"{bigger['id']} gains only {gain:.4f} mean CV AUC (< {need}): keep the simpler {simple['id']}"


def analyse(data_dir: str | Path, contract: dict | None = None) -> dict:
    contract = contract or load_contract()
    meta = load_export_meta(data_dir)
    raw = load_raw(data_dir, contract)
    tables, issues = clean_tables(raw, contract)
    checks = run_checks(
        contract, {**tables, "raw_usage": raw["usage"]}, only={"customers", "invoices", "usage", "tickets", "raw_usage"}
    )
    raise_on_errors(checks)
    export_month = month_index(meta["export"])
    features = build_features(tables, contract, export_month)
    summary = snapshot_summary(features)
    snap_checks = run_checks(contract, {"snapshots": pd.DataFrame(summary)}, only={"snapshots"})
    checks += snap_checks
    raise_on_errors(snap_checks)
    names = feature_names(contract)
    ev = contract["evaluation"]
    train = features[features["split"] == "train"].reset_index(drop=True)
    test = features[features["split"] == "test"].reset_index(drop=True)
    y_test = test["churned"].astype(int)

    experiments, fits, preds = [], {}, {}
    for exp in contract["experiments"]:
        cv = cross_validate(exp, contract, train)
        fits[exp["id"]] = fit_experiment(exp, contract, train)
        preds[exp["id"]] = predict_experiment(exp, contract, fits[exp["id"]], test)
        experiments.append(
            {
                "id": exp["id"],
                "name": exp["name"],
                "kind": exp["kind"],
                "features": experiment_features(exp, contract),
                "cv": cv,
                "test": score_metrics(test, y_test, preds[exp["id"]], ev),
            }
        )
    champion_id, reason = choose_champion(experiments, contract)
    champ = next(e for e in experiments if e["id"] == champion_id)
    fit, p = fits[champion_id], preds[champion_id]
    used = champ["features"]
    means = {f: float(train[f].mean()) for f in used}
    sds = {f: float(train[f].std(ddof=0)) for f in used}
    train_p = predict_logistic(fit, train)
    threshold = quantile7(train_p, 0.9)
    test_m = champ["test"]
    slice_rows = slices(test, y_test, p, ev)
    fair = fairness(slice_rows, ev, contract["cleaning"]["missing_label"])
    reasons = tables["customers"].set_index("customer_id")["cancellation_reason"]
    probe = (train["customer_id"].map(reasons).fillna("").str.strip() != "").astype(int).to_numpy()
    leak = leakage_scan(train, names, probe, ev["leakage_max_single_feature_auc"])
    by_id = {e["id"]: e["test"] for e in experiments}
    verdict = gate(test_m, by_id["B1"], by_id["B0"], fair, leak, contract["gate"])
    training = {
        "export": meta["export"],
        "contract_version": contract["contract_version"],
        "snapshots": contract["snapshots"]["train"],
        "rows": len(train),
        "churners": int(train["churned"].sum()),
    }
    artefact = build_artefact(
        fit,
        champion_id,
        used,
        means,
        threshold,
        float(train["churned"].mean()),
        training,
        {k: test_m[k] for k in ("auc", "average_precision", "brier", "ece", "precision_at_top", "recall_at_top")},
        __version__,
        TRACK,
    )
    importance = sorted(
        (
            {
                "feature": f,
                "coefficient": fit["coefficients"][f],
                "sd": sds[f],
                "standardised": fit["coefficients"][f] * sds[f],
            }
            for f in used
        ),
        key=lambda r: -abs(r["standardised"]),
    )
    metrics = {
        "schema_version": "1.0",
        "generator": {"track": TRACK, "version": __version__},
        "dataset": {
            "export": meta["export"],
            "period_end": meta["period_end"],
            "contract_version": contract["contract_version"],
        },
        "data_quality": {
            "raw_rows": {k: len(v) for k, v in raw.items()},
            "clean_rows": {k: len(v) for k, v in tables.items()},
            "issues": issues,
            "checks": checks,
        },
        "snapshots": summary,
        "split": {
            "train_snapshots": contract["snapshots"]["train"],
            "test_snapshots": contract["snapshots"]["test"],
            "train_rows": len(train),
            "test_rows": len(test),
            "train_churn_rate": float(train["churned"].mean()),
            "test_churn_rate": float(y_test.mean()),
            "folds": [
                {
                    "fold": k,
                    "rows": int((train["fold"] == k).sum()),
                    "customers": int(train.loc[train["fold"] == k, "customer_id"].nunique()),
                    "churners": int(train.loc[train["fold"] == k, "churned"].sum()),
                }
                for k in range(contract["snapshots"]["folds"])
            ],
            "customers_in_two_folds": int(train.groupby("customer_id")["fold"].nunique().gt(1).sum()),
        },
        "leakage": leak,
        "experiments": experiments,
        "champion": {
            "experiment": champion_id,
            "reason": reason,
            "features": used,
            "intercept": fit["intercept"],
            "coefficients": fit["coefficients"],
            "feature_means": means,
            "importance": importance,
            "high_risk_threshold": threshold,
        },
        "test": test_m,
        "calibration": calibration(y_test, p, ev["calibration_bins"]),
        "slices": slice_rows,
        "fairness": fair,
        "gate": verdict,
    }
    return {"metrics": metrics, "artefact": artefact, "features": features}


def write_outputs(result: dict, out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    result["features"].to_csv(out / "features.csv", index=False, lineterminator="\n")
    (out / "metrics.json").write_text(json.dumps(result["metrics"], indent=2) + "\n", encoding="utf-8")
    (out / "model.json").write_text(json.dumps(result["artefact"], indent=2) + "\n", encoding="utf-8")
    m = result["metrics"]
    with open(out / "experiments.jsonl", "w", encoding="utf-8") as fh:
        for e in m["experiments"]:
            line = {
                "run": {
                    "export": m["dataset"]["export"],
                    "contract_version": m["dataset"]["contract_version"],
                    "track": TRACK,
                    "version": __version__,
                },
                "id": e["id"],
                "name": e["name"],
                "features": e["features"],
                "cv_auc_mean": e["cv"]["auc_mean"],
                "cv_auc_sd": e["cv"]["auc_sd"],
                "test_auc": e["test"]["auc"],
                "test_brier": e["test"]["brier"],
                "champion": e["id"] == m["champion"]["experiment"],
            }
            fh.write(json.dumps(line) + "\n")
