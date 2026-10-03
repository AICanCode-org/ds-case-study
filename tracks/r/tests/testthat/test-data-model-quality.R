skip_if_pending("test-data-model-quality.R")
# The evaluation gate as tests: the model ships only if these numbers hold on the out-of-time test months.

by_id <- function() {
  e <- real_result()$metrics$experiments
  stats::setNames(e, vapply(e, function(x) x$id, ""))
}
champ_id <- function() real_result()$metrics$champion$experiment

test_that("the gate passes", {
  expect_true(real_result()$metrics$gate$passed)
})

test_that("the champion beats both baselines", {
  e <- by_id()
  t <- e[[champ_id()]]$test
  g <- CONTRACT$gate
  expect_gte(t$auc, g$min_test_auc)
  expect_gte(t$auc - e$B1$test$auc, g$min_auc_uplift_over_rule)
  expect_lt(t$brier, e$B0$test$brier)
  expect_gt(t$precision_at_top, e$B1$test$precision_at_top)
})

test_that("the champion was chosen on cross-validation, not on the test months", {
  e <- by_id()
  logistic <- Filter(function(x) x$kind == "logistic", e)
  expect_identical(e[[champ_id()]]$cv$auc_mean, max(vapply(logistic, function(x) x$cv$auc_mean, 0)))
})

test_that("cross-validation is stable", {
  for (x in Filter(function(x) x$kind == "logistic", by_id())) expect_lt(x$cv$auc_sd, 0.03)
})

test_that("the model is calibrated and fair enough", {
  m <- real_result()$metrics
  expect_lte(m$calibration$ece, CONTRACT$gate$max_ece)
  expect_lt(abs(m$calibration$mean_pred - m$calibration$observed_rate), 0.02)
  expect_true(m$fairness$passed)
})

test_that("the retention campaign is worth more than the rule", {
  e <- by_id()
  expect_gt(e[[champ_id()]]$test$net_value_inr_per_month, e$B1$test$net_value_inr_per_month)
  expect_gt(e$B1$test$net_value_inr_per_month, 0)
})

test_that("training twice gives identical results", {
  again <- analyse(EXPORT_V10, CONTRACT)
  expect_identical(again$metrics, real_result()$metrics)
  expect_identical(again$artefact$coefficients, real_result()$artefact$coefficients)
})
