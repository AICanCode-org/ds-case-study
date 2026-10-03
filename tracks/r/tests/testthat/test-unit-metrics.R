skip_if_pending("test-unit-metrics.R")

EV <- list(top_percent = 10, calibration_bins = 10, offer_cost_inr = 200, save_rate = 0.25, value_months = 3,
           slices = list("age_band"), min_slice_rows_for_auc = 2, min_slice_churners_for_auc = 1,
           fairness = list(dimension = "age_band", min_churners = 1, max_recall_gap = 0.15))

test_that("the shared metric cases", {
  for (case in CASES$metric_cases) {
    y <- unlist(case$y)
    s <- unlist(case$score)
    p <- unlist(case$prob)
    expect_equal(auc(y, s), case$auc, tolerance = 1e-12, label = case$name)
    expect_equal(average_precision(y, s), case$average_precision, tolerance = 1e-12, label = case$name)
    expect_equal(brier(y, p), case$brier, tolerance = 1e-12)
    expect_equal(log_loss(y, p), case$log_loss, tolerance = 1e-12)
    cal <- calibration(y, p, 10)
    expect_equal(cal$ece, case$ece, tolerance = 1e-12)
    expect_identical(vapply(cal$bins, function(b) b$n, 0L), vapply(case$calibration_bins, function(b) b$n, 0L))
  }
})

test_that("our AUC is yardstick's ROC AUC", {
  case <- CASES$metric_cases[[1]]
  truth <- factor(unlist(case$y), levels = c(1, 0))
  expect_equal(auc(unlist(case$y), unlist(case$score)),
               yardstick::roc_auc_vec(truth, unlist(case$score), event_level = "first"), tolerance = 1e-12)
})

test_that("AUC is undefined with one class; constant scores give one half", {
  expect_true(is.na(auc(c(0, 0), c(0.1, 0.2))))
  expect_true(is.na(average_precision(c(0, 0), c(0.1, 0.2))))
  expect_identical(auc(c(0, 1, 0, 1), rep(0.3, 4)), 0.5)
})

test_that("top_k rounds up without floats", {
  for (case in CASES$top_k) expect_identical(top_k(case$n, case$percent), as.integer(case$k))
})

test_that("type-7 quantile", {
  for (case in CASES$quantile7) expect_equal(quantile7(unlist(case$values), case$q), case$expected, tolerance = 1e-12)
})

frame <- function(n = 20) {
  data.frame(snapshot = rep(c("2026-03", "2026-04"), each = n / 2), customer_id = sprintf("C%05d", seq_len(n) - 1),
             price_inr = 3000, age_band = rep(c("18-24", "25-34"), n / 2))
}

test_that("contacted is the top decile per snapshot, ties by id", {
  f <- frame()
  expect_identical(f$customer_id[contacted(f, rep(0.5, 20), 10)], c("C00000", "C00010"))
})

test_that("capacity metrics and value", {
  f <- frame()
  i <- seq_len(20) - 1
  y <- as.integer(i %in% c(0, 10, 3))
  p <- ifelse(i %in% c(0, 10), 0.9, 0.1)
  m <- capacity_metrics(f, y, p, EV)
  expect_identical(c(m$contacted, m$churners_reached), c(2L, 2L))
  expect_equal(m$precision_at_top, 1)
  expect_equal(m$recall_at_top, 2 / 3)
  expect_equal(m$lift_at_top, 1 / (3 / 20))
  expect_equal(m$net_value_inr_per_month, (2 * 3000 * 0.25 * 3 - 2 * 200) / 2)
})

test_that("slices, fairness and the gate", {
  f <- frame()
  i <- seq_len(20) - 1
  y <- as.integer(i %in% c(0, 1, 10, 11))
  p <- ifelse(i %in% c(0, 10), 0.9, ifelse(i %in% c(1, 11), 0.8, 0.1))
  rows <- slices(f, y, p, EV)
  by <- stats::setNames(rows$age_band, vapply(rows$age_band, function(r) r$value, ""))
  expect_identical(c(by[["18-24"]]$recall_at_top, by[["25-34"]]$recall_at_top), c(1, 0))
  fair <- fairness(rows, EV, "unknown")
  expect_identical(c(fair$recall_gap, fair$passed), c(1, FALSE))
  g <- gate(list(auc = 0.8, ece = 0.01, brier = 0.07), list(auc = 0.7), list(brier = 0.08), fair,
            list(max_feature_auc = 0.7, limit = 0.9, passed = TRUE),
            list(min_test_auc = 0.72, min_auc_uplift_over_rule = 0.03, max_ece = 0.03, max_recall_gap = 0.15))
  failed <- vapply(Filter(function(ch) !ch$passed, g$checks), function(ch) ch$id, "")
  expect_identical(failed, "recall_gap")
  expect_false(g$passed)
})

test_that("the leakage scan flags a perfect feature", {
  train <- data.frame(churned = c(0, 0, 1, 1), a = c(1, 2, 3, 4), b = c(1, 0, 1, 0))
  scan <- leakage_scan(train, c("a", "b"), c(0, 0, 1, 1), 0.9)
  expect_identical(scan$max_feature, "a")
  expect_false(scan$passed)
  expect_identical(scan$probe_auc, 1)
  expect_equal(scan$feature_auc$b, 0.5)
})
