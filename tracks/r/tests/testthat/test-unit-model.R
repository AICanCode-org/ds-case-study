skip_if_pending("test-unit-model.R")

RULES <- list(list(feature = "a", op = ">=", value = 2), list(feature = "b", op = "<=", value = 0))

test_that("the logistic regression matches the shared case", {
  case <- CASES$logistic
  x <- data.frame(x1 = unlist(case$x1), x2 = unlist(case$x2))
  fit <- fit_logistic(x, unlist(case$y))
  expect_equal(fit$intercept, case$intercept, tolerance = 1e-6)
  for (name in names(case$coefficients)) expect_equal(fit$coefficients[[name]], case$coefficients[[name]],
                                                      tolerance = 1e-6)
  expect_s3_class(fit$workflow, "workflow")
})

test_that("training is deterministic", {
  case <- CASES$logistic
  x <- data.frame(x1 = unlist(case$x1), x2 = unlist(case$x2))
  a <- fit_logistic(x, unlist(case$y))
  b <- fit_logistic(x, unlist(case$y))
  expect_identical(a[c("intercept", "coefficients")], b[c("intercept", "coefficients")])
})

test_that("predictions are probabilities", {
  fit <- list(intercept = 0, coefficients = list(x = 1))
  p <- predict_logistic(fit, data.frame(x = c(-50, 0, 50)))
  expect_identical(p[2], 0.5)
  expect_true(p[1] > 0 && p[1] < 1e-20 && abs(p[3] - 1) < 1e-12)
})

test_that("the rule score counts flags", {
  expect_identical(rule_score(data.frame(a = c(0, 2, 5), b = c(1, 0, -1)), RULES), c(0L, 2L, 2L))
})

test_that("the rule baseline is a lookup of training rates", {
  x <- data.frame(a = c(0, 0, 3, 3), b = c(1, 1, 1, 0))
  fit <- fit_rule(x, c(0, 1, 1, 1), RULES)
  expect_identical(as.list(fit$rates), list("0" = 0.5, "1" = 1, "2" = 1))
  unseen <- fit_rule(x[1:2, ], c(0, 1), RULES)
  expect_identical(predict_rule(unseen, x, RULES), rep(0.5, 4))
})

test_that("the prior", {
  expect_identical(predict_prior(fit_prior(c(0, 0, 0, 1)), data.frame(x = 1:2)), c(0.25, 0.25))
})

test_that("the contract folds are an rsample rset with no customer in two folds", {
  train <- data.frame(customer_id = sprintf("C%05d", c(1, 2, 3, 6, 7)), fold = c(1L, 2L, 3L, 1L, 2L))
  rset <- contract_folds(train, 5)
  expect_s3_class(rset, "manual_rset")
  sizes <- vapply(rset$splits, function(s) nrow(rsample::assessment(s)), 0L)
  expect_identical(sizes, c(0L, 2L, 2L, 1L, 0L))
})
