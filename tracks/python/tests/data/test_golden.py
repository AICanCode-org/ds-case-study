"""Golden metrics: the whole metrics.json on the latest export equals the reference all tracks agreed on.
Fix the cause in the code, never the golden file (scripts/parity.py prints the JSON paths that differ)."""

import json
import sys

from tests.conftest import CONTRACT_DIR, REPO

sys.path.insert(0, str(REPO / "scripts"))
import parity


def test_metrics_equal_the_golden_file(result):
    golden = json.loads((CONTRACT_DIR / "golden" / "metrics-2026-07.json").read_text(encoding="utf-8"))
    got = json.loads(json.dumps(result["metrics"]))
    problems = list(parity.diff_json(golden, got))
    assert not problems, "\n".join(problems[:20])


def test_the_model_artefact_equals_the_golden_one(result):
    golden = json.loads((CONTRACT_DIR / "golden" / "model-2026-07.json").read_text(encoding="utf-8"))
    problems = list(parity.diff_json(golden, json.loads(json.dumps(result["artefact"]))))
    assert not problems, "\n".join(problems[:20])


def test_the_cli_writes_the_four_outputs(tmp_path, capsys):
    from churncast.__main__ import main
    from tests.conftest import EXPORT_V11

    out = tmp_path / "out"
    assert main(["run", "--data", str(EXPORT_V11), "--out", str(out)]) == 0
    assert "gate PASSED" in capsys.readouterr().out
    assert sorted(p.name for p in out.iterdir()) == ["experiments.jsonl", "features.csv", "metrics.json", "model.json"]
    lines = (out / "experiments.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x)["id"] for x in lines] == ["B0", "B1", "E1", "E2"]
    assert sum(json.loads(x)["champion"] for x in lines) == 1
    assert parity.main([str(REPO / "contract" / "golden" / "metrics-2026-07.json"), str(out / "metrics.json")]) == 0


def test_v1_1_code_still_reproduces_the_v1_0_release(result_v10):
    """Backward compatibility: on the 2026-05 export every v1.0 field is unchanged; only additions are allowed."""
    for name, got in (("metrics", result_v10["metrics"]), ("model", result_v10["artefact"])):
        golden = json.loads((CONTRACT_DIR / "golden" / f"{name}-2026-05.json").read_text(encoding="utf-8"))
        problems = list(parity.diff_json(golden, json.loads(json.dumps(got)), subset=True))
        assert not problems, "\n".join(problems[:20])


def test_without_labelled_post_deployment_months_there_is_nothing_to_monitor(result_v10):
    assert "monitoring" not in result_v10["metrics"] and "retraining" not in result_v10["metrics"]
    assert result_v10["artefact"]["lineage"] == {
        "parent_model_version": None,
        "trained_on": result_v10["metrics"]["split"]["train_snapshots"],
    }
