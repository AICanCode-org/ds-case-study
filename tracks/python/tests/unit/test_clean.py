from datetime import datetime

import pytest

from churncast.clean import ISSUE_ORDER, month_index, normalise_label, parse_money, parse_with
from tests.conftest import EXPECTED

TS = ["%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M"]


def test_normalise_label():
    assert normalise_label("  PUNE ") == "pune"
    assert normalise_label("") == ""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-01-31 23:00:00", datetime(2026, 1, 31, 23, 0)),
        ("05/02/2026 10:30", datetime(2026, 2, 5, 10, 30)),
        ("2026-02-30 10:00:00", None),
        ("2026/01/05", None),
        ("", None),
    ],
)
def test_two_timestamp_formats_day_first(text, expected):
    assert parse_with(text, TS) == expected


@pytest.mark.parametrize(
    ("text", "rupees"),
    [
        ("3299", 3299.0),
        ("3,299.00", 3299.0),
        ("₹3,299", 3299.0),
        (" 4499.0 ", 4499.0),
        ("-300.00", -300.0),
        ("abc", None),
        ("", None),
    ],
)
def test_money_as_text(text, rupees):
    assert parse_money(text) == rupees


def test_month_index_counts_months():
    assert month_index("2026-01") - month_index("2025-11") == 2


def test_issue_counts_in_order(tiny):
    _, _, issues = tiny
    assert list(issues) == ISSUE_ORDER
    assert issues == EXPECTED["issues"]


def test_clean_row_counts(tiny):
    _, tables, _ = tiny
    assert {k: len(v) for k, v in tables.items()} == EXPECTED["clean_rows"]


def test_labels_are_normalised_and_aliased(tiny):
    _, tables, _ = tiny
    c = tables["customers"].set_index("customer_id")
    assert c.loc["C00002", "city"] == "bengaluru"  # 'Bangalore' is an alias
    assert c.loc["C00004", "acquisition_channel"] == "referral"
    assert c.loc["C00003", "acquisition_channel"] == "unknown"
    assert c.loc["C00003", "signup_date"] == "2025-12-10"  # 10/12/2025 is day first
    assert "C00005" not in c.index  # 2026-02-30 does not exist


def test_resolved_before_created_becomes_unresolved(tiny):
    _, tables, _ = tiny
    t = tables["tickets"].set_index("ticket_id")
    assert t.loc["T000005", "resolved"] is None or t["resolved"].isna()["T000005"]


def test_refunds_are_kept_but_never_charges(tiny):
    _, tables, _ = tiny
    inv = tables["invoices"]
    refunds = inv[inv["kind"] == "refund"]
    assert len(refunds) == 1 and refunds["list_price"].iloc[0] == -300.0
