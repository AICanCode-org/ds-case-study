"""M1 · Cleaning rules of contract/feature-spec.md §2, in the written order. Every rule that drops or changes rows
counts them in `issues`, so rows read = rows kept + rows dropped can be checked (Phase 4 invariants)."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

ISSUE_ORDER = [
    "customers_invalid_signup_date",
    "customers_exact_duplicates",
    "customers_channel_missing",
    "customers_age_band_missing",
    "invoices_exact_duplicates",
    "invoices_orphans",
    "usage_exact_duplicates",
    "usage_negative_counts",
    "usage_orphans",
    "tickets_invalid_created_at",
    "tickets_resolved_before_created",
    "tickets_orphans",
]
COUNTS = ["meals_ordered", "meals_skipped", "late_deliveries", "ratings_count", "ratings_sum"]


def normalise_label(value: str) -> str:
    # TODO(M1) normalise_label: trim + lower-case, before any comparison (' Bangalore' and 'bangalore' are one
    # city). Spec: contract/feature-spec.md §2; tests: clean.
    raise NotImplementedError("TODO(M1) normalise_label: see the comment above")


def parse_with(value: str, formats: list[str]) -> datetime | None:
    # TODO(M1) parse_with: try the contract's formats in order; '05/03/2025' is 5 March (day first). Anything
    # else, or an impossible date such as 31/02, is missing, never a guess. Spec: contract/feature-spec.md §2;
    # tests: clean.
    raise NotImplementedError("TODO(M1) parse_with: see the comment above")


def parse_money(value: str) -> float | None:
    """'₹3,299', '3,299.00', ' 3299.0 ', '-150.00' -> rupees; anything else -> None."""
    # TODO(M1) parse_money: strip the rupee sign, thousands separators and spaces; keep the sign of refunds;
    # '3,299.00' -> 3299. Spec: contract/feature-spec.md §2; tests: clean.
    raise NotImplementedError("TODO(M1) parse_money: see the comment above")


def clean_customers(raw: pd.DataFrame, contract: dict, issues: dict) -> pd.DataFrame:
    # TODO(M1) clean_customers: invalid signup dates go, exact duplicates keep one row, city aliases from the
    # contract, a blank channel or age band becomes 'unknown'. Count every rule in `issues`. Spec:
    # contract/feature-spec.md §2; tests: clean.
    raise NotImplementedError("TODO(M1) clean_customers: see the comment above")


def month_index(value: str) -> int:
    year, month = value.strip().split("-")
    return int(year) * 12 + int(month) - 1


def clean_invoices(raw: pd.DataFrame, customers: pd.DataFrame, contract: dict, issues: dict) -> pd.DataFrame:
    # TODO(M1) clean_invoices: exact duplicates keep one row; invoices of unknown customers are orphans
    # (counted, dropped). A duplicated charge would make a customer look like a renewer twice: check before you
    # join. Spec: contract/feature-spec.md §2; tests: clean.
    raise NotImplementedError("TODO(M1) clean_invoices: see the comment above")


def clean_usage(raw: pd.DataFrame, customers: pd.DataFrame, issues: dict) -> pd.DataFrame:
    # TODO(M1) clean_usage: exact duplicates keep one row; a row with any negative count is dropped (counted),
    # then orphans. Spec: contract/feature-spec.md §2; tests: clean.
    raise NotImplementedError("TODO(M1) clean_usage: see the comment above")


def clean_tickets(raw: pd.DataFrame, customers: pd.DataFrame, contract: dict, issues: dict) -> pd.DataFrame:
    # TODO(M1) clean_tickets: unparseable created_at goes; a resolution before its creation is unknown (resolved
    # = missing, counted), then orphans. Spec: contract/feature-spec.md §2; tests: clean.
    raise NotImplementedError("TODO(M1) clean_tickets: see the comment above")


def clean_tables(raw: dict[str, pd.DataFrame], contract: dict) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    # TODO(M1) clean_tables: call the four cleaners in order; return the tables and the issues in ISSUE_ORDER.
    # Spec: contract/feature-spec.md §2; tests: clean.
    raise NotImplementedError("TODO(M1) clean_tables: see the comment above")
