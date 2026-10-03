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
    return value.strip().lower()


def parse_with(value: str, formats: list[str]) -> datetime | None:
    value = value.strip()
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_money(value: str) -> float | None:
    """'₹3,299', '3,299.00', ' 3299.0 ', '-150.00' -> rupees; anything else -> None."""
    text = value.replace("₹", "").replace(",", "").strip()
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def clean_customers(raw: pd.DataFrame, contract: dict, issues: dict) -> pd.DataFrame:
    rules = contract["cleaning"]
    df = raw.copy()
    df["signup"] = [parse_with(v, rules["date_formats"]) for v in df["signup_date"]]
    bad = df["signup"].isna()
    issues["customers_invalid_signup_date"] = int(bad.sum())
    df = df[~bad]
    before = len(df)
    df = df.drop_duplicates(subset=contract["files"]["customers"]["columns"], keep="first")
    issues["customers_exact_duplicates"] = before - len(df)
    df["customer_id"] = df["customer_id"].str.strip()
    city = df["city"].map(normalise_label)
    df["city"] = city.map(lambda c: rules["city_aliases"].get(c, c))
    missing = rules["missing_label"]
    channel = df["acquisition_channel"].map(normalise_label)
    issues["customers_channel_missing"] = int((channel == "").sum())
    df["acquisition_channel"] = channel.where(channel != "", missing)
    age = df["age_band"].map(normalise_label)
    issues["customers_age_band_missing"] = int((age == "").sum())
    df["age_band"] = age.where(age != "", missing)
    df["city_tier"] = df["city"].map(lambda c: rules["city_tier"].get(c, missing))
    df["signup_month"] = df["signup"].map(lambda d: d.year * 12 + d.month - 1)
    df["signup_date"] = df["signup"].map(lambda d: d.strftime("%Y-%m-%d"))
    cols = [
        "customer_id",
        "signup_date",
        "signup_month",
        "city",
        "city_tier",
        "acquisition_channel",
        "age_band",
        "cancellation_reason",
    ]
    return df[cols].reset_index(drop=True)


def month_index(value: str) -> int:
    year, month = value.strip().split("-")
    return int(year) * 12 + int(month) - 1


def clean_invoices(raw: pd.DataFrame, customers: pd.DataFrame, contract: dict, issues: dict) -> pd.DataFrame:
    before = len(raw)
    df = raw.drop_duplicates(keep="first").copy()
    issues["invoices_exact_duplicates"] = before - len(df)
    for col in ("kind", "plan", "status"):
        df[col] = df[col].map(normalise_label)
    df["list_price"] = df["list_price"].map(parse_money)
    df["discount"] = df["discount"].map(parse_money)
    df["month"] = df["billing_month"].map(month_index)
    known = df["customer_id"].isin(set(customers["customer_id"]))
    issues["invoices_orphans"] = int((~known).sum())
    cols = ["invoice_id", "customer_id", "billing_month", "month", "kind", "plan", "list_price", "discount", "status"]
    return df[known][cols].reset_index(drop=True)


def clean_usage(raw: pd.DataFrame, customers: pd.DataFrame, issues: dict) -> pd.DataFrame:
    before = len(raw)
    df = raw.drop_duplicates(keep="first").copy()
    issues["usage_exact_duplicates"] = before - len(df)
    for col in COUNTS:
        df[col] = df[col].astype(int)
    negative = (df[COUNTS] < 0).any(axis=1)
    issues["usage_negative_counts"] = int(negative.sum())
    df = df[~negative]
    known = df["customer_id"].isin(set(customers["customer_id"]))
    issues["usage_orphans"] = int((~known).sum())
    df = df[known].copy()
    df["month"] = df["month"].map(month_index)
    return df[["customer_id", "month", *COUNTS]].reset_index(drop=True)


def clean_tickets(raw: pd.DataFrame, customers: pd.DataFrame, contract: dict, issues: dict) -> pd.DataFrame:
    formats = contract["cleaning"]["timestamp_formats"]
    df = raw.copy()
    df["created"] = [parse_with(v, formats) for v in df["created_at"]]
    bad = df["created"].isna()
    issues["tickets_invalid_created_at"] = int(bad.sum())
    df = df[~bad].copy()
    df["resolved"] = [parse_with(v, formats) if v.strip() else None for v in df["resolved_at"]]
    backwards = df["resolved"].notna() & (df["resolved"] < df["created"])
    issues["tickets_resolved_before_created"] = int(backwards.sum())
    df.loc[backwards, "resolved"] = None
    df["category"] = df["category"].map(normalise_label)
    known = df["customer_id"].isin(set(customers["customer_id"]))
    issues["tickets_orphans"] = int((~known).sum())
    return df[known][["ticket_id", "customer_id", "created", "category", "resolved"]].reset_index(drop=True)


def clean_tables(raw: dict[str, pd.DataFrame], contract: dict) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    issues: dict[str, int] = {}
    customers = clean_customers(raw["customers"], contract, issues)
    tables = {
        "customers": customers,
        "invoices": clean_invoices(raw["invoices"], customers, contract, issues),
        "usage": clean_usage(raw["usage"], customers, issues),
        "tickets": clean_tickets(raw["tickets"], customers, contract, issues),
    }
    return tables, {k: issues[k] for k in ISSUE_ORDER}
