skip_if_pending("test-unit-monitoring.R")
# M7 unit tests: PSI, the calibration offset and the fairness recall gap on tiny inputs.

test_that("PSI edges are type-7 deciles without duplicates", {
  expect_identical(psi_edges(1:11, 10L), as.numeric(2:10))
  expect_equal(psi_edges(c(rep(0, 8), 1, 2), 10L), c(0, 0.2, 1.1))
})

test_that("a value on an edge falls in the lower bin", {
  expect_identical(bin_shares(c(1, 2, 2.5, 3, 4), c(2, 3)), c(0.4, 0.4, 0.2))
  expect_identical(bin_shares(c(5, 6), c(2, 3)), c(0, 0, 1))
})

test_that("PSI is zero for the same distribution and floors empty bins", {
  ref <- c(0.25, 0.25, 0.5)
  expect_identical(psi(ref, ref, 1e-4), 0)
  expected <- (0.5 - 0.25) * log(0.5 / 0.25) + (1e-4 - 0.25) * log(1e-4 / 0.25)
  expect_equal(psi(ref, c(0.5, 0, 0.5), 1e-4), expected)
})

test_that("PSI status thresholds", {
  mon <- list(psi_watch = 0.1, psi_drift = 0.25)
  expect_identical(vapply(c(0.0999, 0.1, 0.2499, 0.25), psi_status, "", mon = mon),
                   c("stable", "watch", "watch", "drift"))
})

test_that("the calibration offset matches the mean", {
  eta <- c(-2, -1, 0, 1)
  d <- calibration_offset(eta, c(0L, 1L, 1L, 1L))
  expect_equal(sum(stats::plogis(eta + d)), 3, tolerance = 1e-10)
  expect_equal(calibration_offset(rep(0, 4), c(0L, 0L, 1L, 1L)), 0, tolerance = 1e-12)
})

test_that("the recall gap ignores small and unknown groups", {
  frame <- data.frame(snapshot = "2026-06", customer_id = sprintf("C%05d", 0:7),
                      age_band = c(rep("a", 4), rep("b", 3), "unknown"))
  y <- c(1, 1, 0, 0, 1, 0, 0, 1)
  p <- c(0.9, 0.1, 0.2, 0.3, 0.8, 0.4, 0.5, 0.95)
  ev <- list(top_percent = 25, fairness = list(dimension = "age_band", min_churners = 1))
  expect_equal(recall_gap(frame, y, p, ev, "unknown"), 0.5)
})

test_that("the reference profile keeps arrays even for one edge", {
  rows <- data.frame(x = c(1, 1, 1, 1))
  prof <- reference_profile(rows, "x", c(0.1, 0.2, 0.3, 0.4), 10L)
  json <- jsonlite::fromJSON(to_json(prof), simplifyVector = FALSE)
  expect_identical(json$features$x$edges, list(1L))
  expect_identical(json$features$x$shares, list(1L, 0L))  # one edge, two bins: all values in the lower one
})
