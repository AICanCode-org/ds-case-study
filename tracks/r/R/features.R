# M3 · Snapshots, labels and point-in-time features (contract/feature-spec.md §3-§4).
#
# A snapshot is the end of month M. Everything a feature uses must have been known before S, the first instant of
# month M+1: invoices and usage of months <= M, tickets created before S, and a resolution only if it happened
# before S. The label looks at month M+1 only, and is never available to a feature.

SLICE_COLUMNS <- c("city", "city_tier", "age_band", "channel", "plan", "price_inr")
SPLITS <- c("train", "test", "recent", "holdout", "score")

month_label <- function(index) sprintf("%04d-%02d", index %/% 12L, index %% 12L + 1L)

month_start <- function(index) as.POSIXct(sprintf("%s-01 00:00:00", month_label(index)), tz = "UTC")

#' Every contract snapshot the export covers; recent/holdout (1.1) also need their label month in the export.
snapshot_months <- function(contract, export_month) {
  months <- unlist(lapply(SPLITS, function(s) {
    m <- month_index(unlist(contract$snapshots[[s]]))
    lag <- if (s %in% c("recent", "holdout")) 1L else 0L
    m[m + lag <= export_month]
  }))
  sort(unique(months))
}

split_of <- function(month, contract) {
  label <- month_label(month)
  for (name in SPLITS) if (label %in% unlist(contract$snapshots[[name]])) return(name)
  "none"
}

fold_of <- function(customer_id, folds) as.integer(substring(customer_id, 2)) %% as.integer(folds)

paid_charges <- function(invoices) {
  paid <- invoices[invoices$kind == "charge" & invoices$status == "paid", , drop = FALSE]
  paid <- paid[order(paid$customer_id, paid$month, paid$invoice_id, method = "radix"), , drop = FALSE]
  paid[!duplicated(paid[c("customer_id", "month")]), , drop = FALSE]
}

#' The value of `col` in `table` for each customer of `ids` (`table` has one row per customer), 0 when absent.
lookup <- function(ids, table, col, default = 0) {
  v <- table[[col]][match(ids, table$customer_id)]
  ifelse(is.na(v), default, v)
}

count_by_customer <- function(ids, customer_ids) {
  counts <- table(customer_ids)
  v <- as.integer(counts[ids])
  ifelse(is.na(v), 0L, v)
}

build_snapshot <- function(tables, contract, month, export_month, paid) {
  customers <- tables$customers
  usage <- tables$usage
  tickets <- tables$tickets
  invoices <- tables$invoices
  base <- paid[paid$month == month, c("customer_id", "plan", "list_price", "discount")]
  df <- dplyr::inner_join(base, customers, by = "customer_id", relationship = "one-to-one")
  df <- df[order(df$customer_id, method = "radix"), , drop = FALSE]
  ids <- df$customer_id
  df$snapshot <- rep(month_label(month), nrow(df))
  df$churned <- if (month + 1L <= export_month) {
    as.integer(!(ids %in% paid$customer_id[paid$month == month + 1L]))
  } else {
    rep(NA_integer_, nrow(df))
  }
  tenure <- month - df$signup_month
  df$tenure_months <- tenure
  df$is_new <- as.integer(tenure < 3)
  df$plan_standard <- as.integer(df$plan == "standard")
  df$plan_premium <- as.integer(df$plan == "premium")
  df$discount_share <- df$discount / df$list_price
  prev <- paid[paid$month == month - 1L, , drop = FALSE]
  prev_price <- prev$list_price[match(ids, prev$customer_id)]
  change <- (df$list_price - prev_price) / prev_price
  df$price_change_pct <- ifelse(is.na(change), 0, change)
  u <- lapply(0:2, function(lag) usage[usage$month == month - lag, , drop = FALSE])
  meals <- lapply(u, function(x) lookup(ids, x, "meals_ordered"))
  skipped0 <- lookup(ids, u[[1]], "meals_skipped")
  df$meals_last_month <- meals[[1]]
  denom <- meals[[1]] + skipped0
  df$skip_rate_last_month <- ifelse(denom > 0, skipped0 / pmax(denom, 1), 0)
  prior_n <- pmin(tenure, 2)
  prior_sum <- ifelse(tenure >= 1, meals[[2]], 0) + ifelse(tenure >= 2, meals[[3]], 0)
  df$meals_trend <- ifelse(prior_n > 0, meals[[1]] - prior_sum / pmax(prior_n, 1), 0)
  meals3 <- meals[[1]] + meals[[2]] + meals[[3]]
  late3 <- Reduce(`+`, lapply(u, function(x) lookup(ids, x, "late_deliveries")))
  df$late_rate_3m <- ifelse(meals3 > 0, late3 / pmax(meals3, 1), 0)
  rc <- Reduce(`+`, lapply(u, function(x) lookup(ids, x, "ratings_count")))
  rs <- Reduce(`+`, lapply(u, function(x) lookup(ids, x, "ratings_sum")))
  df$avg_rating_3m <- ifelse(rc > 0, rs / pmax(rc, 1), as.numeric(contract$cleaning$rating_default))
  df$rating_missing <- as.integer(rc == 0)
  cut <- month_start(month + 1L)
  known <- tickets[tickets$created < cut, , drop = FALSE]
  recent <- known$customer_id[known$created >= cut - 90 * 86400]
  still_open <- known$customer_id[is.na(known$resolved) | known$resolved >= cut]
  df$tickets_90d <- count_by_customer(ids, recent)
  df$open_tickets <- count_by_customer(ids, still_open)
  failed <- invoices$customer_id[invoices$kind == "charge" & invoices$status == "failed" &
                                   invoices$month >= month - 2L & invoices$month <= month]
  df$failed_payments_3m <- count_by_customer(ids, failed)
  df$channel <- df$acquisition_channel
  df$price_inr <- df$list_price
  df
}

#' One row per (customer, snapshot), sorted by snapshot then customer_id.
build_features <- function(tables, contract, export_month) {
  paid <- paid_charges(tables$invoices)
  parts <- lapply(snapshot_months(contract, export_month), function(m) {
    build_snapshot(tables, contract, m, export_month, paid)
  })
  df <- do.call(rbind, parts)
  df$split <- vapply(month_index(df$snapshot), split_of, character(1), contract = contract)
  df$fold <- fold_of(df$customer_id, contract$snapshots$folds)
  names <- feature_names(contract)
  for (n in names) df[[n]] <- as.numeric(df[[n]])
  out <- df[c("customer_id", "snapshot", "split", "fold", "churned", names, SLICE_COLUMNS)]
  out <- out[order(out$snapshot, out$customer_id, method = "radix"), , drop = FALSE]
  rownames(out) <- NULL
  out
}

snapshot_summary <- function(features) {
  lapply(split(features, features$snapshot), function(g) {
    labelled <- !anyNA(g$churned)
    churned <- if (labelled) sum(g$churned) else NULL
    list(snapshot = g$snapshot[1], split = g$split[1], rows = nrow(g), churned = churned,
         churn_rate = if (labelled) churned / nrow(g) else NULL)
  }) |> unname()
}
