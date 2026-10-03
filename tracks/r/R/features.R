# M3 · Snapshots, labels and point-in-time features (contract/feature-spec.md §3-§4).
#
# A snapshot is the end of month M. Everything a feature uses must have been known before S, the first instant of
# month M+1: invoices and usage of months <= M, tickets created before S, and a resolution only if it happened
# before S. The label looks at month M+1 only, and is never available to a feature.

SLICE_COLUMNS <- c("city", "city_tier", "age_band", "channel", "plan", "price_inr")
SPLITS <- c("train", "test", "recent", "holdout", "score")

month_label <- function(index) sprintf("%04d-%02d", index %/% 12L, index %% 12L + 1L)

month_start <- function(index) as.POSIXct(sprintf("%s-01 00:00:00", month_label(index)), tz = "UTC")

snapshot_months <- function(contract, export_month) {
  # TODO(M3) snapshot_months: the contract snapshots the export covers (a snapshot needs its month in the
  # export). Spec: contract/feature-spec.md §3-§4; tests: features.
  stop("TODO(M3) snapshot_months: see the comment above")
}

split_of <- function(month, contract) {
  # TODO(M3) split_of: train or test (from the contract) for a snapshot month. Spec: contract/feature-spec.md
  # §3-§4; tests: features.
  stop("TODO(M3) split_of: see the comment above")
}

fold_of <- function(customer_id, folds) {
  # TODO(M3) fold_of: customer number mod folds (C00042 -> 2 with 5 folds): a customer never sits in two folds.
  # Spec: contract/feature-spec.md §3-§4; tests: features.
  stop("TODO(M3) fold_of: see the comment above")
}

paid_charges <- function(invoices) {
  # TODO(M3) paid_charges: one paid charge per customer and month (the lowest invoice_id wins); refunds and
  # failed payments are not renewals. Spec: contract/feature-spec.md §3-§4; tests: features.
  stop("TODO(M3) paid_charges: see the comment above")
}

#' The value of `col` in `table` for each customer of `ids` (`table` has one row per customer), 0 when absent.
lookup <- function(ids, table, col, default = 0) {
  # TODO(M3) lookup: a per-customer value from a table, with a default for customers who have no row. Spec:
  # contract/feature-spec.md §3-§4; tests: features.
  stop("TODO(M3) lookup: see the comment above")
}

count_by_customer <- function(ids, customer_ids) {
  # TODO(M3) count_by_customer: how many rows each customer has (0 for none). Spec: contract/feature-spec.md
  # §3-§4; tests: features.
  stop("TODO(M3) count_by_customer: see the comment above")
}

build_snapshot <- function(tables, contract, month, export_month, paid) {
  # TODO(M3) build_snapshot: THE leakage trap. Everything a feature uses must be known before S = month_start(M
  # + 1): invoices and usage of months <= M, tickets created before S, a resolution only if before S. The label
  # looks at month M + 1 only. Never touch cancellation_reason. Spec: contract/feature-spec.md §3-§4; tests:
  # features.
  stop("TODO(M3) build_snapshot: see the comment above")
}

#' One row per (customer, snapshot), sorted by snapshot then customer_id.
build_features <- function(tables, contract, export_month) {
  # TODO(M3) build_features: every snapshot, sorted by snapshot then customer_id, with split and fold; features
  # as floats. Spec: contract/feature-spec.md §3-§4; tests: features.
  stop("TODO(M3) build_features: see the comment above")
}

snapshot_summary <- function(features) {
  # TODO(M3) snapshot_summary: rows, churners and churn rate per snapshot (null when the label month is not in
  # the export). Spec: contract/feature-spec.md §3-§4; tests: features.
  stop("TODO(M3) snapshot_summary: see the comment above")
}
