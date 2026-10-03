skip_if_pending("test-unit-artefact.R")

FIT <- list(intercept = -2, coefficients = list(a = 0.5, b = -1))
artefact <- function() {
  build_artefact(FIT, "E2", c("a", "b"), list(a = 1, b = 0.5), 0.3, 0.1, list(export = "2026-05"),
                 list(auc = 0.8), "1.0.0", "r")
}

test_that("the artefact shape", {
  a <- artefact()
  expect_identical(a$schema_version, "1.0")
  expect_identical(names(a$coefficients), unlist(a$features))
  expect_identical(a$generator, list(track = "r", version = "1.0.0"))
  json <- jsonlite::fromJSON(to_json(a), simplifyVector = FALSE)
  expect_identical(json$features, list("a", "b"))
})

test_that("the score is the logistic of the linear predictor", {
  expect_equal(score(artefact(), list(a = 2, b = 1)), 1 / (1 + exp(-(-2 + 1 - 1))))
})

test_that("contributions add up and are sorted", {
  a <- artefact()
  row <- list(a = 3, b = 0)
  c <- contributions(a, row)
  expect_identical(vapply(c, function(r) r$feature, ""), c("a", "b"))
  at_mean <- a$intercept + sum(unlist(a$coefficients) * unlist(a$feature_means))
  p <- score(a, row)
  expect_equal(sum(vapply(c, function(r) r$contribution, 0)), log(p / (1 - p)) - at_mean)
})
