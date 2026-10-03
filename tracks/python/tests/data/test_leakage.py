"""Leakage: nothing the model sees may come from after the snapshot, and no column may be too good to be true."""

from churncast.clean import clean_tables, month_index
from churncast.features import build_features
from churncast.load import load_raw
from tests.conftest import EXPORT_V10


def test_no_model_feature_is_suspiciously_good(result):
    leak = result["metrics"]["leakage"]
    assert leak["passed"]
    assert leak["max_feature_auc"] < leak["limit"]


def test_the_leaky_column_would_have_looked_like_the_best_feature(result):
    leak = result["metrics"]["leakage"]
    assert leak["probe_auc"] > leak["max_feature_auc"] + 0.1  # why it must never be a feature


def test_cancellation_reason_is_not_a_feature(result):
    assert not any("reason" in f or "cancel" in f for f in result["artefact"]["features"])


def test_rows_from_the_future_do_not_change_past_features(contract, export_copy):
    """Point in time: append a ticket and a usage row dated after the last snapshot's cut-off; the features of
    every snapshot whose label is known must not change."""
    path = export_copy(EXPORT_V10)
    tables, _ = clean_tables(load_raw(path, contract), contract)
    before = build_features(tables, contract, month_index("2026-05"))
    with open(path / "tickets.csv", "a", encoding="utf-8") as fh:
        fh.write("T999999,C00002,2026-05-01 00:00:00,cancellation,\n")
    tables, _ = clean_tables(load_raw(path, contract), contract)
    after = build_features(tables, contract, month_index("2026-05"))
    mask = before["snapshot"] <= "2026-04"
    assert before[mask].equals(after[mask])
