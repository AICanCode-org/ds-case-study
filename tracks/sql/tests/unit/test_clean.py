from datetime import datetime

import pytest

from churncast_sql.runner import load_and_clean
from tests.conftest import EXPECTED, TINY, rows

ISSUE_ORDER = list(EXPECTED["issues"])


@pytest.fixture
def cleaned(con, contract):
    load_and_clean(con, TINY, contract)
    return con


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
def test_two_timestamp_formats_day_first(cleaned, text, expected):
    assert cleaned.execute("SELECT parse_ts(?)", [text]).fetchone()[0] == expected


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
def test_money_as_text(cleaned, text, rupees):
    assert cleaned.execute("SELECT parse_money(?)", [text]).fetchone()[0] == rupees


def test_month_index_counts_months(cleaned):
    assert cleaned.execute("SELECT month_index('2026-01') - month_index('2025-11')").fetchone()[0] == 2


def test_issue_counts_in_order(cleaned):
    got = rows(cleaned, "SELECT issue, n FROM issues ORDER BY pos")
    assert [r["issue"] for r in got] == ISSUE_ORDER
    assert {r["issue"]: r["n"] for r in got} == EXPECTED["issues"]


def test_clean_row_counts(cleaned):
    got = {t: cleaned.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in EXPECTED["clean_rows"]}
    assert got == EXPECTED["clean_rows"]


def test_labels_are_normalised_and_aliased(cleaned):
    c = {r["customer_id"]: r for r in rows(cleaned, "SELECT * FROM customers")}
    assert c["C00002"]["city"] == "bengaluru"  # 'Bangalore' is an alias
    assert c["C00004"]["acquisition_channel"] == "referral"
    assert c["C00003"]["acquisition_channel"] == "unknown"
    assert c["C00003"]["signup_date"] == "2025-12-10"  # 10/12/2025 is day first
    assert "C00005" not in c  # 2026-02-30 does not exist


def test_resolved_before_created_becomes_unresolved(cleaned):
    assert cleaned.execute("SELECT resolved FROM tickets WHERE ticket_id = 'T000005'").fetchone()[0] is None


def test_refunds_are_kept_but_never_charges(cleaned):
    got = rows(cleaned, "SELECT list_price FROM invoices WHERE kind = 'refund'")
    assert got == [{"list_price": -300.0}]
