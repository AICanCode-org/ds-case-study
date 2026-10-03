"""M3 · Snapshots, labels and point-in-time features (contract/feature-spec.md §3-§4).

A snapshot is the end of month M. Everything a feature uses must have been known before S, the first instant of
month M+1: invoices and usage of months <= M, tickets created before S, and a resolution only if it happened
before S. The label looks at month M+1 only, and is never available to a feature.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

SLICE_COLUMNS = ["city", "city_tier", "age_band", "channel", "plan", "price_inr"]


def month_label(index: int) -> str:
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def month_start(index: int) -> datetime:
    return datetime(index // 12, index % 12 + 1, 1)


def snapshot_months(contract: dict, export_month: int) -> list[int]:
    """Every contract snapshot the export covers (the label month may be missing: label = None)."""
    # TODO(M3) snapshot_months: the contract snapshots the export covers (a snapshot needs its month in the
    # export). Spec: contract/feature-spec.md §3-§4; tests: features.
    raise NotImplementedError("TODO(M3) snapshot_months: see the comment above")


def split_of(month: int, contract: dict) -> str:
    # TODO(M3) split_of: train or test (from the contract) for a snapshot month. Spec: contract/feature-spec.md
    # §3-§4; tests: features.
    raise NotImplementedError("TODO(M3) split_of: see the comment above")


def fold_of(customer_id: str, folds: int) -> int:
    # TODO(M3) fold_of: customer number mod folds (C00042 -> 2 with 5 folds): a customer never sits in two
    # folds. Spec: contract/feature-spec.md §3-§4; tests: features.
    raise NotImplementedError("TODO(M3) fold_of: see the comment above")


def paid_charges(invoices: pd.DataFrame) -> pd.DataFrame:
    # TODO(M3) paid_charges: one paid charge per customer and month (the lowest invoice_id wins); refunds and
    # failed payments are not renewals. Spec: contract/feature-spec.md §3-§4; tests: features.
    raise NotImplementedError("TODO(M3) paid_charges: see the comment above")


def build_snapshot(tables: dict, contract: dict, month: int, export_month: int) -> pd.DataFrame:
    # TODO(M3) build_snapshot: THE leakage trap. Everything a feature uses must be known before S =
    # month_start(M + 1): invoices and usage of months <= M, tickets created before S, a resolution only if
    # before S. The label looks at month M + 1 only. Never touch cancellation_reason. Spec:
    # contract/feature-spec.md §3-§4; tests: features.
    raise NotImplementedError("TODO(M3) build_snapshot: see the comment above")


def build_features(tables: dict, contract: dict, export_month: int) -> pd.DataFrame:
    """One row per (customer, snapshot), sorted by snapshot then customer_id."""
    # TODO(M3) build_features: every snapshot, sorted by snapshot then customer_id, with split and fold;
    # features as floats. Spec: contract/feature-spec.md §3-§4; tests: features.
    raise NotImplementedError("TODO(M3) build_features: see the comment above")


def snapshot_summary(features: pd.DataFrame) -> list[dict]:
    # TODO(M3) snapshot_summary: rows, churners and churn rate per snapshot (null when the label month is not in
    # the export). Spec: contract/feature-spec.md §3-§4; tests: features.
    raise NotImplementedError("TODO(M3) snapshot_summary: see the comment above")
