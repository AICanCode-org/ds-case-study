skip_if_pending("test-data-invariants.R")
# Properties that must hold for ANY export, not just this one.

test_that("rows read = rows kept + rows dropped", {
  dq <- real_result()$metrics$data_quality
  i <- dq$issues
  dropped <- list(
    customers = i$customers_invalid_signup_date + i$customers_exact_duplicates,
    invoices = i$invoices_exact_duplicates + i$invoices_orphans,
    usage = i$usage_exact_duplicates + i$usage_negative_counts + i$usage_orphans,
    tickets = i$tickets_invalid_created_at + i$tickets_orphans
  )
  for (t in names(dq$raw_rows)) expect_identical(dq$raw_rows[[t]], dq$clean_rows[[t]] + dropped[[t]], label = t)
})

test_that("every feature is inside its contract range", {
  f <- real_result()$features
  for (spec in CONTRACT$features) {
    col <- f[[spec$name]]
    expect_false(anyNA(col), label = spec$name)
    expect_true(all(col >= spec$min & col <= spec$max), label = spec$name)
    if (spec$type == "binary") expect_true(all(col %in% c(0, 1)), label = spec$name)
  }
})

test_that("one row per customer and snapshot", {
  f <- real_result()$features
  expect_false(anyDuplicated(f[c("customer_id", "snapshot")]) > 0)
})

test_that("no customer sits in two folds and test comes after train", {
  s <- real_result()$metrics$split
  expect_identical(s$customers_in_two_folds, 0L)
  expect_true(max(unlist(s$train_snapshots)) < min(unlist(s$test_snapshots)))
  expect_identical(sum(vapply(s$folds, function(f) f$rows, 0L)), s$train_rows)
})

test_that("labels exist for every train and test row", {
  f <- real_result()$features
  expect_false(anyNA(f$churned[f$split %in% c("train", "test")]))
})

test_that("contributions explain the prediction exactly", {
  r <- real_result()
  a <- r$artefact
  row <- as.list(r$features[1, feature_names(CONTRACT)])
  at_mean <- a$intercept + sum(unlist(a$coefficients) * unlist(a$feature_means))
  p <- score(a, row)
  total <- sum(vapply(contributions(a, row), function(x) x$contribution, 0))
  expect_equal(at_mean + total, log(p / (1 - p)), tolerance = 1e-9)
})
