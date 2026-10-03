"""M7 on the real 2026-07 export: monitoring catches the June price change, the challenger beats the champion."""

import json

import pytest

from churncast.__main__ import main
from tests.conftest import CONTRACT_DIR, EXPORT_V11


@pytest.fixture(scope="module")
def mon(result):
    return result["metrics"]["monitoring"]


@pytest.fixture(scope="module")
def rt(result):
    return result["metrics"]["retraining"]


def test_post_deployment_snapshots_are_split_by_role(result):
    s = result["metrics"]["split"]
    assert s["train_snapshots"][-1] == "2026-02" and s["test_snapshots"] == ["2026-03", "2026-04"]
    roles = {d["snapshot"]: d["split"] for d in result["metrics"]["monitoring"]["drift"]}
    assert roles == {"2026-05": "recent", "2026-06": "holdout", "2026-07": "score"}


def test_the_june_price_change_is_flagged_as_drift(mon):
    june = next(d for d in mon["drift"] if d["snapshot"] == "2026-06")
    assert june["features_drift"] == ["price_change_pct"]
    assert june["feature_psi"]["price_change_pct"] > 1.0
    may = next(d for d in mon["drift"] if d["snapshot"] == "2026-05")
    assert may["features_drift"] == []


def test_the_deployed_model_still_ranks_but_is_miscalibrated(mon):
    june = next(p for p in mon["performance"] if p["snapshot"] == "2026-06")
    assert june["auc"] > 0.72  # ranking is fine ...
    assert june["ece"] > 0.03 and june["observed_rate"] - june["mean_pred"] > 0.05  # ... it under-predicts churn
    assert mon["status"] == "retrain"


def test_the_score_month_is_never_labelled(mon):
    assert [p["snapshot"] for p in mon["performance"]] == ["2026-05", "2026-06"]


def test_the_challenger_is_refitted_then_recalibrated(rt):
    c = rt["challenger"]
    assert c["refit_snapshots"] == [f"2025-{m:02d}" for m in range(9, 13)] + [f"2026-{m:02d}" for m in range(1, 5)]
    assert c["calibration_snapshot"] == "2026-05" and c["calibration_offset"] > 0  # churn rose: shift up


def test_the_challenger_wins_on_the_holdout_month(rt):
    ch, cc = rt["champion_holdout"], rt["challenger_holdout"]
    assert cc["brier"] < ch["brier"] and cc["ece"] < 0.03 and cc["auc"] >= ch["auc"] - 0.005
    assert rt["gate"]["passed"] and rt["decision"] == "promote"
    assert [c["id"] for c in rt["gate"]["checks"]] == ["auc_not_worse", "brier_improves", "ece", "recall_gap"]


def test_the_promoted_artefact_records_its_lineage(result, rt):
    a = result["artefact"]
    assert a["model_version"] == "1.1.0" and a["schema_version"] == "1.1"
    assert a["lineage"]["parent_model_version"] == "1.0.0" and a["lineage"]["decision"] == "promote"
    assert a["intercept"] == rt["challenger"]["intercept"]
    ref = a["monitoring_reference"]
    assert set(ref["features"]) == set(a["features"]) and ref["rows"] == rt["challenger"]["refit_rows"]
    assert all(abs(sum(v["shares"]) - 1) < 1e-12 for v in [*ref["features"].values(), ref["score"]])


def test_the_v1_0_contract_rejects_the_new_export(tmp_path, capsys):
    """The incident behind the 1.1.0 contract: marketing launched an influencer channel in June 2026."""
    old = CONTRACT_DIR / "history" / "data-contract-1.0.0.yaml"
    code = main(["run", "--data", str(EXPORT_V11), "--out", str(tmp_path / "out"), "--contract", str(old)])
    assert code == 3
    assert "customers.channel.accepted" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_the_committed_v1_1_model_is_the_golden_one():
    a = json.loads((CONTRACT_DIR.parent / "models" / "churncast-1.1.0.json").read_text(encoding="utf-8"))
    b = json.loads((CONTRACT_DIR / "golden" / "model-2026-07.json").read_text(encoding="utf-8"))
    assert {k: v for k, v in a.items() if k != "generator"} == {k: v for k, v in b.items() if k != "generator"}
