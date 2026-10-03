# M1 · Cleaning rules of contract/feature-spec.md §2, in the written order. Every rule that drops or changes rows
# counts them in `issues`, so rows read = rows kept + rows dropped can be checked (Phase 4 invariants).

ISSUE_ORDER <- c(
  "customers_invalid_signup_date", "customers_exact_duplicates", "customers_channel_missing",
  "customers_age_band_missing", "invoices_exact_duplicates", "invoices_orphans", "usage_exact_duplicates",
  "usage_negative_counts", "usage_orphans", "tickets_invalid_created_at", "tickets_resolved_before_created",
  "tickets_orphans"
)
COUNTS <- c("meals_ordered", "meals_skipped", "late_deliveries", "ratings_count", "ratings_sum")

# strptime() ignores trailing text and accepts one-digit fields, so each format also has an exact pattern
FORMAT_PATTERNS <- c(
  "%Y-%m-%d %H:%M:%S" = "^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$",
  "%d/%m/%Y %H:%M" = "^\\d{2}/\\d{2}/\\d{4} \\d{2}:\\d{2}$",
  "%Y-%m-%d" = "^\\d{4}-\\d{2}-\\d{2}$",
  "%d/%m/%Y" = "^\\d{2}/\\d{2}/\\d{4}$"
)

normalise_label <- function(x) {
  # TODO(M1) normalise_label: trim + lower-case, before any comparison (' Bangalore' and 'bangalore' are one
  # city). Spec: contract/feature-spec.md §2; tests: clean.
  stop("TODO(M1) normalise_label: see the comment above")
}

#' The first format that parses the whole value; NA when none does. Times are UTC (no daylight saving).
parse_with <- function(values, formats) {
  # TODO(M1) parse_with: try the contract's formats in order; '05/03/2025' is 5 March (day first). Anything
  # else, or an impossible date such as 31/02, is missing, never a guess. Spec: contract/feature-spec.md §2;
  # tests: clean.
  stop("TODO(M1) parse_with: see the comment above")
}

#' "₹3,299", "3,299.00", " 3299.0 ", "-150.00" -> rupees; anything else -> NA.
parse_money <- function(x) {
  # TODO(M1) parse_money: strip the rupee sign, thousands separators and spaces; keep the sign of refunds;
  # '3,299.00' -> 3299. Spec: contract/feature-spec.md §2; tests: clean.
  stop("TODO(M1) parse_money: see the comment above")
}

month_index <- function(x) {
  parts <- strsplit(trimws(x), "-", fixed = TRUE)
  vapply(parts, function(p) as.integer(p[1]) * 12L + as.integer(p[2]) - 1L, integer(1))
}

clean_customers <- function(raw, contract, issues) {
  # TODO(M1) clean_customers: invalid signup dates go, exact duplicates keep one row, city aliases from the
  # contract, a blank channel or age band becomes 'unknown'. Count every rule in `issues`. Spec:
  # contract/feature-spec.md §2; tests: clean.
  stop("TODO(M1) clean_customers: see the comment above")
}

clean_invoices <- function(raw, customers, issues) {
  # TODO(M1) clean_invoices: exact duplicates keep one row; invoices of unknown customers are orphans (counted,
  # dropped). A duplicated charge would make a customer look like a renewer twice: check before you join. Spec:
  # contract/feature-spec.md §2; tests: clean.
  stop("TODO(M1) clean_invoices: see the comment above")
}

clean_usage <- function(raw, customers, issues) {
  # TODO(M1) clean_usage: exact duplicates keep one row; a row with any negative count is dropped (counted),
  # then orphans. Spec: contract/feature-spec.md §2; tests: clean.
  stop("TODO(M1) clean_usage: see the comment above")
}

clean_tickets <- function(raw, customers, contract, issues) {
  # TODO(M1) clean_tickets: unparseable created_at goes; a resolution before its creation is unknown (resolved =
  # missing, counted), then orphans. Spec: contract/feature-spec.md §2; tests: clean.
  stop("TODO(M1) clean_tickets: see the comment above")
}

clean_tables <- function(raw, contract) {
  # TODO(M1) clean_tables: call the four cleaners in order; return the tables and the issues in ISSUE_ORDER.
  # Spec: contract/feature-spec.md §2; tests: clean.
  stop("TODO(M1) clean_tables: see the comment above")
}
