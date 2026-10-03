"""Leakage: nothing the model sees may come from after the snapshot, and no column may be too good to be true."""

from churncast_sql.runner import connect, load_and_clean, run_script
from tests.conftest import EXPORT_V10, rows


def test_no_model_feature_is_suspiciously_good(result):
    leak = result["metrics"]["leakage"]
    assert leak["passed"]
    assert leak["max_feature_auc"] < leak["limit"]


def test_the_leaky_column_would_have_looked_like_the_best_feature(result):
    leak = result["metrics"]["leakage"]
    assert leak["probe_auc"] > leak["max_feature_auc"] + 0.1  # why it must never be a feature


def test_cancellation_reason_is_not_a_feature(result):
    assert not any("reason" in f or "cancel" in f for f in result["artefact"]["features"])


def features_of(path, contract) -> list[dict]:
    con = connect()
    try:
        load_and_clean(con, path, contract)
        run_script(con, "03_features.sql")
        return rows(con, "SELECT * FROM features WHERE snapshot <= '2026-04' ORDER BY snapshot, customer_id")
    finally:
        con.close()


def test_rows_from_the_future_do_not_change_past_features(contract, export_copy):
    """Point in time: append a ticket dated after the April snapshot's cut-off; no labelled snapshot may change."""
    path = export_copy(EXPORT_V10)
    before = features_of(path, contract)
    with open(path / "tickets.csv", "a", encoding="utf-8") as fh:
        fh.write("T999999,C00002,2026-05-01 00:00:00,cancellation,\n")
    assert features_of(path, contract) == before
