import pytest

from churncast_sql.fit import fit_logistic
from churncast_sql.runner import load_and_clean, run_script, score_sql
from tests.conftest import CASES, TINY, rows


def test_logistic_regression_matches_the_shared_case():
    case = CASES["logistic"]
    x = list(zip(case["x1"], case["x2"], strict=True))
    fit = fit_logistic(x, case["y"], ["x1", "x2"])
    assert fit["intercept"] == pytest.approx(case["intercept"], abs=1e-6)
    for name, b in case["coefficients"].items():
        assert fit["coefficients"][name] == pytest.approx(b, abs=1e-6)


def test_training_is_deterministic():
    case = CASES["logistic"]
    x = list(zip(case["x1"], case["x2"], strict=True))
    assert fit_logistic(x, case["y"], ["x1", "x2"]) == fit_logistic(x, case["y"], ["x1", "x2"])


def test_scoring_sql_is_the_logistic_of_the_linear_predictor(con):
    fit = {"intercept": -2.0, "coefficients": {"a": 0.5, "b": -1.0}}
    con.execute("CREATE TABLE f AS SELECT 2.0 AS a, 1.0 AS b")
    eta = con.execute(f"SELECT {score_sql(fit)} FROM f").fetchone()[0]
    assert eta == -2.0 + 0.5 * 2 - 1.0


@pytest.fixture
def modelled(con, tiny_contract):
    load_and_clean(con, TINY, tiny_contract)
    run_script(con, "03_features.sql")
    run_script(con, "04_models.sql")
    return con


def test_rule_points_count_the_flags(modelled, tiny_contract):
    feats = {(r["customer_id"], r["snapshot"]): r for r in rows(modelled, "SELECT * FROM features")}
    for r in rows(modelled, "SELECT * FROM rule_points"):
        f = feats[(r["customer_id"], r["snapshot"])]
        want = sum(
            (f[x["feature"]] >= x["value"]) if x["op"] == ">=" else (f[x["feature"]] <= x["value"])
            for x in tiny_contract["rule_baseline"]
        )
        assert r["points"] == want


def test_every_stage_fits_on_other_rows_than_it_scores(modelled):
    overlap = modelled.execute(
        "SELECT count(*) FROM stage_rows AS a JOIN stage_rows AS b USING (stage, customer_id, snapshot) "
        "WHERE a.role = 'fit' AND b.role = 'eval' AND stage <> 'train'"
    ).fetchone()[0]
    assert overlap == 0


def test_baselines_are_scored_for_every_eval_row(modelled):
    evals = modelled.execute("SELECT count(*) FROM stage_rows WHERE role = 'eval'").fetchone()[0]
    for exp in ("B0", "B1"):
        assert modelled.execute("SELECT count(*) FROM scored WHERE exp_id = ?", [exp]).fetchone()[0] == evals
    prior = rows(modelled, "SELECT DISTINCT p FROM scored WHERE exp_id = 'B0' AND stage = 'test'")
    want = modelled.execute("SELECT avg(churned) FROM features WHERE split = 'train'").fetchone()[0]
    assert prior == [{"p": want}]
