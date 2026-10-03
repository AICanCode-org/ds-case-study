skip_if_pending("test-data-leakage.R")
# Leakage: nothing the model sees may come from after the snapshot, and no column may be too good to be true.

test_that("no model feature is suspiciously good", {
  leak <- real_result()$metrics$leakage
  expect_true(leak$passed)
  expect_lt(leak$max_feature_auc, leak$limit)
})

test_that("the leaky column would have looked like the best feature", {
  leak <- real_result()$metrics$leakage
  expect_gt(leak$probe_auc, leak$max_feature_auc + 0.1)
})

test_that("cancellation_reason is not a feature", {
  expect_false(any(grepl("reason|cancel", unlist(real_result()$artefact$features))))
})

test_that("rows from the future do not change past features", {
  path <- export_copy(EXPORT_V10)
  features <- function() {
    f <- build_features(clean_tables(load_raw(path, CONTRACT), CONTRACT)$tables, CONTRACT, month_index("2026-05"))
    f[f$snapshot <= "2026-04", ]
  }
  before <- features()
  append_line(file.path(path, "tickets.csv"), "T999999,C00002,2026-05-01 00:00:00,cancellation,")
  expect_identical(features(), before)
})
