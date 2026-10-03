import math

import pandas as pd

from churncast.clean import month_index
from churncast.contract import feature_names
from churncast.features import build_features, fold_of, month_label, snapshot_summary, split_of
from tests.conftest import EXPECTED


def test_features_match_the_expected_tiny_table(tiny, tiny_contract):
    _, tables, _ = tiny
    got = build_features(tables, tiny_contract, month_index("2026-03"))
    want = EXPECTED["features"]
    assert len(got) == len(want)
    for row, exp in zip(got.to_dict(orient="records"), want, strict=True):
        for key, value in exp.items():
            if isinstance(value, float):
                assert math.isclose(row[key], value, rel_tol=1e-9, abs_tol=1e-12), (row["customer_id"], key)
            else:
                assert row[key] == value, (row["customer_id"], row["snapshot"], key)


def test_column_order_is_the_contract_order(tiny, tiny_contract):
    _, tables, _ = tiny
    got = build_features(tables, tiny_contract, month_index("2026-03"))
    names = feature_names(tiny_contract)
    assert list(got.columns[5 : 5 + len(names)]) == names


def test_a_ticket_after_the_snapshot_is_invisible(tiny, tiny_contract):
    """C00002 asks to cancel on 2 March: the February snapshot (cut-off 1 March) must not see it."""
    _, tables, _ = tiny
    got = build_features(tables, tiny_contract, month_index("2026-03")).set_index(["customer_id", "snapshot"])
    assert got.loc[("C00002", "2026-02"), "tickets_90d"] == 1  # the billing ticket only


def test_the_label_needs_the_next_month(tiny, tiny_contract):
    _, tables, _ = tiny
    got = build_features(tables, tiny_contract, month_index("2026-02"))
    assert got[got["snapshot"] == "2026-02"]["churned"].isna().all()


def test_folds_and_splits():
    assert fold_of("C00042", 5) == 2
    assert month_label(month_index("2025-12")) == "2025-12"
    assert split_of(month_index("2026-01"), {"snapshots": {"train": ["2026-01"], "test": []}}) == "train"
    assert split_of(month_index("2027-01"), {"snapshots": {"train": [], "test": []}}) == "none"


def test_snapshot_summary_counts_churners():
    df = pd.DataFrame({"snapshot": ["a", "a", "b"], "split": ["train"] * 3, "churned": [1, 0, pd.NA]})
    s = snapshot_summary(df)
    assert s[0] == {"snapshot": "a", "split": "train", "rows": 2, "churned": 1, "churn_rate": 0.5}
    assert s[1]["churned"] is None and s[1]["churn_rate"] is None
