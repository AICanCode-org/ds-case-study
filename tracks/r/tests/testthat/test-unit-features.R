skip_if_pending("test-unit-features.R")

tiny_features <- function(export = "2026-03") {
  build_features(tiny()$tables, tiny_contract(), month_index(export))
}

test_that("features match the expected tiny table", {
  got <- tiny_features()
  want <- EXPECTED$features
  expect_identical(nrow(got), length(want))
  for (i in seq_along(want)) {
    for (key in names(want[[i]])) {
      value <- want[[i]][[key]]
      if (is.double(value)) {
        expect_equal(got[[key]][i], value, tolerance = 1e-9, label = paste(got$customer_id[i], key))
      } else {
        expect_equal(got[[key]][i], value, label = paste(got$customer_id[i], got$snapshot[i], key))
      }
    }
  }
})

test_that("columns come in the contract order", {
  names <- feature_names(CONTRACT)
  expect_identical(names(tiny_features())[5 + seq_along(names)], names)
})

test_that("a ticket after the snapshot is invisible", {
  got <- tiny_features()
  expect_identical(got$tickets_90d[got$customer_id == "C00002" & got$snapshot == "2026-02"], 1)
})

test_that("the label needs the next month", {
  got <- tiny_features("2026-02")
  expect_true(all(is.na(got$churned[got$snapshot == "2026-02"])))
  s <- snapshot_summary(got)
  last <- s[[length(s)]]
  expect_null(last$churned)
  expect_null(last$churn_rate)
})

test_that("folds and splits", {
  expect_identical(fold_of("C00042", 5), 2L)
  expect_identical(month_label(month_index("2025-12")), "2025-12")
  expect_identical(split_of(month_index("2026-01"), list(snapshots = list(train = list("2026-01")))), "train")
  expect_identical(split_of(month_index("2027-01"), list(snapshots = list(train = list()))), "none")
})

test_that("the snapshot summary counts churners", {
  df <- data.frame(snapshot = c("a", "a", "b"), split = "train", churned = c(1L, 0L, NA))
  s <- snapshot_summary(df)
  expect_identical(s[[1]], list(snapshot = "a", split = "train", rows = 2L, churned = 1L, churn_rate = 0.5))
})
