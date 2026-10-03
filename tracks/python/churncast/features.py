"""M3 · Snapshots, labels and point-in-time features (contract/feature-spec.md §3-§4).

A snapshot is the end of month M. Everything a feature uses must have been known before S, the first instant of
month M+1: invoices and usage of months <= M, tickets created before S, and a resolution only if it happened
before S. The label looks at month M+1 only, and is never available to a feature.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from .clean import month_index
from .contract import feature_names

SLICE_COLUMNS = ["city", "city_tier", "age_band", "channel", "plan", "price_inr"]


def month_label(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_start(index: int) -> datetime:
    return datetime(index // 12, index % 12 + 1, 1)


def snapshot_months(contract: dict, export_month: int) -> list[int]:
    """Every contract snapshot the export covers (the label month may be missing: label = None)."""
    months = [month_index(m) for m in contract["snapshots"]["train"] + contract["snapshots"]["test"]]
    months += [month_index(m) for k in ("recent", "holdout") for m in contract["snapshots"].get(k, [])]
    months += [month_index(m) for m in contract["snapshots"].get("score", [])]
    return sorted(m for m in set(months) if m <= export_month)


def split_of(month: int, contract: dict) -> str:
    label = month_label(month)
    for name in ("train", "test", "recent", "holdout", "score"):
        if label in contract["snapshots"].get(name, []):
            return name
    return "none"


def fold_of(customer_id: str, folds: int) -> int:
    return int(customer_id[1:]) % folds


def paid_charges(invoices: pd.DataFrame) -> pd.DataFrame:
    paid = invoices[(invoices["kind"] == "charge") & (invoices["status"] == "paid")]
    return paid.sort_values(["customer_id", "month", "invoice_id"]).drop_duplicates(["customer_id", "month"])


def build_snapshot(tables: dict, contract: dict, month: int, export_month: int) -> pd.DataFrame:
    customers, invoices, usage, tickets = (tables[k] for k in ("customers", "invoices", "usage", "tickets"))
    paid = paid_charges(invoices)
    base = paid[paid["month"] == month][["customer_id", "plan", "list_price", "discount"]]
    df = base.merge(customers, on="customer_id", how="inner", validate="one_to_one")
    df = df.sort_values("customer_id").reset_index(drop=True)
    df.insert(1, "snapshot", month_label(month))
    # label: still paying in M+1?
    if month + 1 <= export_month:
        renewed = set(paid.loc[paid["month"] == month + 1, "customer_id"])
        df["churned"] = (~df["customer_id"].isin(renewed)).astype(int)
    else:
        df["churned"] = pd.NA
    # plan, price and discount of month M
    df["tenure_months"] = month - df["signup_month"]
    df["is_new"] = (df["tenure_months"] < 3).astype(int)
    df["plan_standard"] = (df["plan"] == "standard").astype(int)
    df["plan_premium"] = (df["plan"] == "premium").astype(int)
    df["discount_share"] = df["discount"] / df["list_price"]
    prev = paid[paid["month"] == month - 1].set_index("customer_id")["list_price"]
    prev_price = df["customer_id"].map(prev)
    df["price_change_pct"] = ((df["list_price"] - prev_price) / prev_price).fillna(0.0)
    # usage: month M, M-1, M-2 (a missing month counts as zero)
    u = usage[usage["customer_id"].isin(df["customer_id"]) & usage["month"].between(month - 2, month)]
    wide = {}
    for lag in (0, 1, 2):
        part = u[u["month"] == month - lag].set_index("customer_id")
        for col in ("meals_ordered", "meals_skipped", "late_deliveries", "ratings_count", "ratings_sum"):
            wide[(col, lag)] = df["customer_id"].map(part[col]).fillna(0).astype(int).to_numpy()
    meals0, skipped0 = wide[("meals_ordered", 0)], wide[("meals_skipped", 0)]
    df["meals_last_month"] = meals0
    denom = meals0 + skipped0
    df["skip_rate_last_month"] = np.where(denom > 0, skipped0 / np.where(denom > 0, denom, 1), 0.0)
    tenure = df["tenure_months"].to_numpy()
    prior_n = np.minimum(tenure, 2)
    prior_sum = np.where(tenure >= 1, wide[("meals_ordered", 1)], 0) + np.where(
        tenure >= 2, wide[("meals_ordered", 2)], 0
    )
    df["meals_trend"] = np.where(prior_n > 0, meals0 - prior_sum / np.where(prior_n > 0, prior_n, 1), 0.0)
    meals3 = sum(wide[("meals_ordered", lag)] for lag in (0, 1, 2))
    late3 = sum(wide[("late_deliveries", lag)] for lag in (0, 1, 2))
    df["late_rate_3m"] = np.where(meals3 > 0, late3 / np.where(meals3 > 0, meals3, 1), 0.0)
    rc = sum(wide[("ratings_count", lag)] for lag in (0, 1, 2))
    rs = sum(wide[("ratings_sum", lag)] for lag in (0, 1, 2))
    default = float(contract["cleaning"]["rating_default"])
    df["avg_rating_3m"] = np.where(rc > 0, rs / np.where(rc > 0, rc, 1), default)
    df["rating_missing"] = (rc == 0).astype(int)
    # tickets known at S
    cut = month_start(month + 1)
    t = tickets[tickets["customer_id"].isin(df["customer_id"]) & (tickets["created"] < cut)]
    recent = t[t["created"] >= cut - timedelta(days=90)].groupby("customer_id").size()
    still_open = t[t["resolved"].isna() | (t["resolved"] >= cut)].groupby("customer_id").size()
    df["tickets_90d"] = df["customer_id"].map(recent).fillna(0).astype(int)
    df["open_tickets"] = df["customer_id"].map(still_open).fillna(0).astype(int)
    failed = (
        invoices[
            (invoices["kind"] == "charge")
            & (invoices["status"] == "failed")
            & invoices["month"].between(month - 2, month)
        ]
        .groupby("customer_id")
        .size()
    )
    df["failed_payments_3m"] = df["customer_id"].map(failed).fillna(0).astype(int)
    df["channel"] = df["acquisition_channel"]
    df["price_inr"] = df["list_price"]
    return df


def build_features(tables: dict, contract: dict, export_month: int) -> pd.DataFrame:
    """One row per (customer, snapshot), sorted by snapshot then customer_id."""
    parts = [build_snapshot(tables, contract, m, export_month) for m in snapshot_months(contract, export_month)]
    df = pd.concat(parts, ignore_index=True)
    df["split"] = df["snapshot"].map(lambda s: split_of(month_index(s), contract))
    df["fold"] = df["customer_id"].map(lambda c: fold_of(c, contract["snapshots"]["folds"]))
    cols = ["customer_id", "snapshot", "split", "fold", "churned", *feature_names(contract), *SLICE_COLUMNS]
    out = df[cols].copy()
    for name in feature_names(contract):
        out[name] = out[name].astype(float)
    return out.sort_values(["snapshot", "customer_id"]).reset_index(drop=True)


def snapshot_summary(features: pd.DataFrame) -> list[dict]:
    rows = []
    for snap, g in features.groupby("snapshot", sort=True):
        labelled = g["churned"].notna().all()
        churned = int(g["churned"].sum()) if labelled else None
        rows.append(
            {
                "snapshot": snap,
                "split": g["split"].iloc[0],
                "rows": len(g),
                "churned": churned,
                "churn_rate": churned / len(g) if labelled else None,
            }
        )
    return rows
