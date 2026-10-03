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

TRACK = "python"


def experiment_features(exp: dict, contract: dict) -> list[str]:
    # TODO(M5) experiment_features: the features of a logistic experiment (core or all); none for the baselines.
    # Spec: contract/feature-spec.md §5-§7 and contract/metrics.schema.json; tests: cli.
    raise NotImplementedError("TODO(M5) experiment_features: see the comment above")


def fit_experiment(exp: dict, contract: dict, rows: pd.DataFrame) -> dict:
    # TODO(M5) fit_experiment: fit one experiment (prior, rule or logistic) on some rows. Spec:
    # contract/feature-spec.md §5-§7 and contract/metrics.schema.json; tests: cli.
    raise NotImplementedError("TODO(M5) fit_experiment: see the comment above")


def predict_experiment(exp: dict, contract: dict, fit: dict, rows: pd.DataFrame) -> np.ndarray:
    # TODO(M5) predict_experiment: predict one fitted experiment on some rows. Spec: contract/feature-spec.md
    # §5-§7 and contract/metrics.schema.json; tests: cli.
    raise NotImplementedError("TODO(M5) predict_experiment: see the comment above")


def cross_validate(exp: dict, contract: dict, train: pd.DataFrame) -> dict:
    # TODO(M5) cross_validate: 5-fold grouped CV on the training rows: fit on the other folds, score the
    # held-out fold; mean and sample SD of the fold AUCs. Spec: contract/feature-spec.md §5-§7 and
    # contract/metrics.schema.json; tests: cli.
    raise NotImplementedError("TODO(M5) cross_validate: see the comment above")


def choose_champion(experiments: list[dict], contract: dict) -> tuple[str, str]:
    # TODO(M5) choose_champion: the bigger logistic experiment only if its mean CV AUC beats the simpler one by
    # the contract's margin; the reason in words. Spec: contract/feature-spec.md §5-§7 and
    # contract/metrics.schema.json; tests: cli.
    raise NotImplementedError("TODO(M5) choose_champion: see the comment above")


def analyse(data_dir: str | Path, contract: dict | None = None) -> dict:
    # TODO(M5) analyse: the whole run: load, clean, checks, features, experiments (CV, then the test months
    # once), champion, evaluation, gate, artefact. Returns metrics, artefact and features. Spec:
    # contract/feature-spec.md §5-§7 and contract/metrics.schema.json; tests: cli.
    raise NotImplementedError("TODO(M5) analyse: see the comment above")


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
