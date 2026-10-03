"""M7 on the real 2026-07 export: monitoring catches the June price change, the challenger beats the champion."""

import json

import pytest

from churncast_sql.__main__ import main
from tests.conftest import CONTRACT_DIR, EXPORT_V11, rows


@pytest.fixture(scope="module")
def mon(result):
    return result["metrics"]["monitoring"]


@pytest.fixture(scope="module")
def rt(result):
    return result["metrics"]["retraining"]


def test_post_deployment_snapshots_are_split_by_role(run):
    con, _ = run
    got = rows(con, "SELECT snapshot, split FROM snapshots WHERE split NOT IN ('train', 'test') ORDER BY snapshot")
    assert [(r["snapshot"], r["split"]) for r in got] == [
        ("2026-05", "recent"),
        ("2026-06", "holdout"),
        ("2026-07", "score"),
    ]


def test_the_june_price_change_is_flagged_as_drift(run, mon):
    con, _ = run
    june = next(d for d in mon["drift"] if d["snapshot"] == "2026-06")
    assert june["features_drift"] == ["price_change_pct"]
    top = rows(con, "SELECT var FROM drift WHERE snapshot = '2026-06' ORDER BY psi DESC LIMIT 1")[0]
    assert top["var"] == "price_change_pct"


def test_every_bin_profile_sums_to_one(run):
    con, _ = run
    sums = con.execute("SELECT grp, var, sum(share) AS s FROM monitor_shares GROUP BY grp, var").fetchall()
    assert sums and all(abs(s - 1) < 1e-12 for _, _, s in sums)


def test_the_deployed_model_still_ranks_but_is_miscalibrated(mon):
    june = next(p for p in mon["performance"] if p["snapshot"] == "2026-06")
    assert june["auc"] > 0.72
    assert june["ece"] > 0.03 and june["observed_rate"] - june["mean_pred"] > 0.05
    assert mon["status"] == "retrain"
    assert [p["snapshot"] for p in mon["performance"]] == ["2026-05", "2026-06"]


def test_the_challenger_wins_on_the_holdout_month(rt):
    ch, cc = rt["champion_holdout"], rt["challenger_holdout"]
    assert rt["challenger"]["calibration_snapshot"] == "2026-05" and rt["challenger"]["calibration_offset"] > 0
    assert cc["brier"] < ch["brier"] and cc["ece"] < 0.03 and cc["auc"] >= ch["auc"] - 0.005
    assert rt["gate"]["passed"] and rt["decision"] == "promote"


def test_the_promoted_artefact_records_its_lineage(result, rt):
    a = result["artefact"]
    assert a["model_version"] == "1.1.0" and a["lineage"]["parent_model_version"] == "1.0.0"
    assert a["lineage"]["decision"] == "promote" and a["intercept"] == rt["challenger"]["intercept"]
    assert a["monitoring_reference"]["rows"] == rt["challenger"]["refit_rows"]


def test_the_v1_0_contract_rejects_the_new_export(tmp_path, capsys):
    """The incident behind the 1.1.0 contract: marketing launched an influencer channel in June 2026."""
    old = CONTRACT_DIR / "history" / "data-contract-1.0.0.yaml"
    code = main(["run", "--data", str(EXPORT_V11), "--out", str(tmp_path / "out"), "--contract", str(old)])
    assert code == 3
    assert "customers.channel.accepted" in capsys.readouterr().err


def test_the_deployed_model_path_can_be_overridden(monkeypatch, contract, tmp_path):
    from churncast_sql.runner import deployed_path

    monkeypatch.setenv("DEPLOYED_MODEL_PATH", str(tmp_path / "m.json"))
    assert deployed_path(contract) == tmp_path / "m.json"
    monkeypatch.delenv("DEPLOYED_MODEL_PATH")
    assert json.loads(deployed_path(contract).read_text(encoding="utf-8"))["model_version"] == "1.0.0"
