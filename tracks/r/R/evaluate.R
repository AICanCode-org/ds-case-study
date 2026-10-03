# M4-M5 · Evaluation (contract/feature-spec.md §6): the metrics written out by hand so every track computes exactly
# the same number (tests compare the AUC with yardstick::roc_auc_vec), plus calibration, the retention-capacity
# view (top 10 % per month), slices, fairness, leakage and the gate.

EPS <- 1e-15

#' Area under the ROC curve = P(score of a churner > score of a stayer), ties count 1/2 (average ranks).
auc <- function(y, p) {
  y <- as.integer(y)
  n_pos <- sum(y)
  n_neg <- length(y) - n_pos
  if (n_pos == 0 || n_neg == 0) return(NA_real_)
  ranks <- rank(as.numeric(p), ties.method = "average")
  (sum(ranks[y == 1]) - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
}

#' Sum over distinct thresholds (high to low) of (recall_k - recall_k-1) * precision_k.
average_precision <- function(y, p) {
  y <- as.integer(y)
  n_pos <- sum(y)
  if (n_pos == 0) return(NA_real_)
  o <- order(as.numeric(p), decreasing = TRUE)
  ps <- as.numeric(p)[o]
  last <- c(ps[-1] != ps[-length(ps)], TRUE)  # the last row of each group of equal scores
  tp <- cumsum(y[o])[last]
  n <- seq_along(ps)[last]
  recall <- tp / n_pos
  sum(diff(c(0, recall)) * (tp / n))
}

brier <- function(y, p) mean((as.numeric(p) - as.numeric(y))^2)

log_loss <- function(y, p) {
  y <- as.numeric(y)
  p <- pmin(pmax(as.numeric(p), EPS), 1 - EPS)
  -mean(y * log(p) + (1 - y) * log(1 - p))
}

calibration <- function(y, p, bins) {
  y <- as.numeric(y)
  p <- as.numeric(p)
  b <- pmin(floor(p * bins), bins - 1)
  rows <- lapply(seq_len(bins) - 1L, function(k) {
    m <- b == k
    n <- sum(m)
    list(bin = k, lower = k / bins, upper = (k + 1) / bins, n = n,
         mean_pred = if (n > 0) mean(p[m]) else NULL, observed = if (n > 0) mean(y[m]) else NULL)
  })
  ece <- 0
  for (r in rows) if (r$n > 0) ece <- ece + r$n / length(p) * abs(r$mean_pred - r$observed)
  list(bins = rows, ece = ece, mean_pred = mean(p), observed_rate = mean(y))
}

#' ceil(n * percent / 100) in integers: no floating-point surprise.
top_k <- function(n, percent) (as.integer(n) * as.integer(percent) + 99L) %/% 100L

#' TRUE for the top `percent` % of each snapshot by risk (ties: lower customer_id first).
contacted <- function(frame, p, percent) {
  flag <- logical(nrow(frame))
  for (s in sort(unique(frame$snapshot))) {
    idx <- which(frame$snapshot == s)
    o <- idx[order(-p[idx], frame$customer_id[idx], method = "radix")]
    flag[o[seq_len(top_k(length(idx), percent))]] <- TRUE
  }
  flag
}

capacity_metrics <- function(frame, y, p, ev) {
  y <- as.integer(y)
  c <- contacted(frame, p, ev$top_percent)
  hits <- sum(y[c])
  precision <- hits / sum(c)
  saved <- sum(y[c] * frame$price_inr[c]) * ev$save_rate * ev$value_months
  list(
    contacted = sum(c),
    churners_reached = hits,
    precision_at_top = precision,
    recall_at_top = hits / sum(y),
    lift_at_top = precision / mean(y),
    net_value_inr_per_month = (saved - ev$offer_cost_inr * sum(c)) / length(unique(frame$snapshot))
  )
}

score_metrics <- function(frame, y, p, ev) {
  c(list(auc = auc(y, p), average_precision = average_precision(y, p), brier = brier(y, p),
         log_loss = log_loss(y, p), ece = calibration(y, p, ev$calibration_bins)$ece),
    capacity_metrics(frame, y, p, ev))
}

slices <- function(frame, y, p, ev) {
  y <- as.integer(y)
  c <- contacted(frame, p, ev$top_percent)
  out <- list()
  for (dim in unlist(ev$slices)) {
    values <- as.character(frame[[dim]])
    out[[dim]] <- lapply(sort(unique(values), method = "radix"), function(v) {
      m <- values == v
      n <- sum(m)
      churners <- sum(y[m])
      enough <- n >= ev$min_slice_rows_for_auc && min(churners, n - churners) >= ev$min_slice_churners_for_auc
      list(value = v, n = n, churners = churners, churn_rate = churners / n, mean_pred = mean(p[m]),
           auc = if (enough) auc(y[m], p[m]) else NULL, contacted = sum(c[m]), flagged_rate = sum(c[m]) / n,
           recall_at_top = if (churners > 0) sum(c[m] & y[m] == 1) / churners else NULL)
    })
  }
  out
}

fairness <- function(slice_rows, ev, missing) {
  f <- ev$fairness
  groups <- Filter(function(r) r$value != missing && r$churners >= f$min_churners, slice_rows[[f$dimension]])
  recalls <- vapply(groups, function(r) r$recall_at_top, numeric(1))
  flagged <- vapply(groups, function(r) r$flagged_rate, numeric(1))
  gap <- max(recalls) - min(recalls)
  list(dimension = f$dimension, groups = lapply(groups, function(r) r$value), recall_gap = gap,
       flagged_rate_ratio = if (max(flagged) > 0) min(flagged) / max(flagged) else NULL,
       max_recall_gap = f$max_recall_gap, passed = gap <= f$max_recall_gap)
}

#' Single-feature AUC (folded to >= 0.5) of every model feature on the training rows, and of the leaky probe.
leakage_scan <- function(train, features, probe, limit) {
  y <- as.integer(train$churned)
  per <- lapply(features, function(name) {
    a <- auc(y, train[[name]])
    max(a, 1 - a)
  })
  names(per) <- features
  worst <- features[which.max(unlist(per))]  # the first one in contract order on a tie
  pa <- auc(y, probe)
  list(feature_auc = per, max_feature = worst, max_feature_auc = per[[worst]], limit = limit,
       probe = "customers.cancellation_reason is filled", probe_auc = max(pa, 1 - pa),
       passed = per[[worst]] < limit)
}

gate <- function(test, rule_test, prior_test, fair, leak, g) {
  checks <- list(
    list(id = "test_auc", value = test$auc, threshold = g$min_test_auc, passed = test$auc >= g$min_test_auc),
    list(id = "auc_uplift_over_rule", value = test$auc - rule_test$auc, threshold = g$min_auc_uplift_over_rule,
         passed = test$auc - rule_test$auc >= g$min_auc_uplift_over_rule),
    list(id = "ece", value = test$ece, threshold = g$max_ece, passed = test$ece <= g$max_ece),
    list(id = "brier_below_prior", value = test$brier, threshold = prior_test$brier,
         passed = test$brier < prior_test$brier),
    list(id = "recall_gap", value = fair$recall_gap, threshold = g$max_recall_gap,
         passed = fair$recall_gap <= g$max_recall_gap),
    list(id = "leakage_scan", value = leak$max_feature_auc, threshold = leak$limit, passed = leak$passed)
  )
  list(checks = checks, passed = all(vapply(checks, function(ch) isTRUE(ch$passed), logical(1))))
}

#' Type-7 quantile (R's and numpy's default): linear interpolation between order statistics.
quantile7 <- function(values, q) unname(stats::quantile(as.numeric(values), q, type = 7))
