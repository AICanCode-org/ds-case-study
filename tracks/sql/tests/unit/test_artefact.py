import math

from churncast_sql.runner import SCHEMA_VERSION, write_outputs
from tests.conftest import rows


def test_artefact_shape(result):
    a = result["artefact"]
    assert a["schema_version"] == SCHEMA_VERSION == "1.1"
    assert list(a["coefficients"]) == a["features"] == list(a["feature_means"])
    assert a["generator"] == {"track": "sql", "version": "1.1.0"}
    assert 0 < a["high_risk_threshold"] < 1


def test_the_artefact_scores_like_the_sql(run):
    con, result = run
    a = result["artefact"]
    row = rows(con, "SELECT * FROM features WHERE split = 'test' ORDER BY snapshot, customer_id LIMIT 1")[0]
    eta = a["intercept"] + sum(b * row[f] for f, b in a["coefficients"].items())
    p_sql = con.execute(
        "SELECT p FROM post_scored WHERE model = 'challenger' AND customer_id = ? AND snapshot = ?",
        [row["customer_id"], row["snapshot"]],
    ).fetchone()[0]
    assert math.isclose(1 / (1 + math.exp(-eta)), p_sql, rel_tol=1e-12)


def test_write_outputs(run, contract, tmp_path):
    con, result = run
    write_outputs(con, result, contract, tmp_path)
    header = (tmp_path / "features.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header[:5] == ["customer_id", "snapshot", "split", "fold", "churned"]
    assert header[-6:] == ["city", "city_tier", "age_band", "channel", "plan", "price_inr"]
