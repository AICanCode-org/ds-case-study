"""The evaluation gate as tests: the model ships only if these numbers hold on the out-of-time test months."""

from churncast_sql.runner import analyse, connect
from tests.conftest import EXPORT_V11


def by_id(result):
    return {e["id"]: e for e in result["metrics"]["experiments"]}


def test_the_gate_passes(result):
    gate = result["metrics"]["gate"]
    assert gate["passed"], [c for c in gate["checks"] if not c["passed"]]


def test_the_champion_beats_both_baselines(result, contract):
    e = by_id(result)
    champ = result["metrics"]["champion"]["experiment"]
    g = contract["gate"]
    assert e[champ]["test"]["auc"] >= g["min_test_auc"]
    assert e[champ]["test"]["auc"] - e["B1"]["test"]["auc"] >= g["min_auc_uplift_over_rule"]
    assert e[champ]["test"]["brier"] < e["B0"]["test"]["brier"]
    assert e[champ]["test"]["precision_at_top"] > e["B1"]["test"]["precision_at_top"]


def test_the_champion_was_chosen_on_cross_validation_not_on_the_test_months(result):
    e = by_id(result)
    champ = result["metrics"]["champion"]["experiment"]
    assert e[champ]["cv"]["auc_mean"] == max(x["cv"]["auc_mean"] for x in e.values() if x["kind"] == "logistic")


def test_cross_validation_is_stable(result):
    for e in result["metrics"]["experiments"]:
        if e["kind"] == "logistic":
            assert e["cv"]["auc_sd"] < 0.03, e["id"]


def test_the_model_is_calibrated_and_fair_enough(result, contract):
    m = result["metrics"]
    assert m["calibration"]["ece"] <= contract["gate"]["max_ece"]
    assert abs(m["calibration"]["mean_pred"] - m["calibration"]["observed_rate"]) < 0.02
    assert m["fairness"]["passed"]


def test_the_retention_campaign_is_worth_more_than_the_rule(result):
    e = by_id(result)
    champ = result["metrics"]["champion"]["experiment"]
    assert e[champ]["test"]["net_value_inr_per_month"] > e["B1"]["test"]["net_value_inr_per_month"] > 0


def test_training_twice_gives_identical_results(result, contract):
    con = connect()
    try:
        again = analyse(con, EXPORT_V11, contract)
    finally:
        con.close()
    assert again["metrics"] == result["metrics"]
    assert again["artefact"] == result["artefact"]
