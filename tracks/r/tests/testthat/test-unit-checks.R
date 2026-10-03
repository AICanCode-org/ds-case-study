skip_if_pending("test-unit-checks.R")

chk <- function(...) modifyList(list(id = "x", table = "t", severity = "error"), list(...))
tbl <- function(df) list(t = df)

test_that("unique counts the extra rows", {
  r <- run_check(chk(type = "unique", column = "a"), tbl(data.frame(a = c("1", "1", "2", "2", "2"))))
  expect_identical(r$failing_rows, 3L)
})

test_that("unique on a compound key", {
  r <- run_check(chk(type = "unique", column = list("a", "b")), tbl(data.frame(a = c("1", "1"), b = c("x", "y"))))
  expect_identical(r$status, "pass")
})

test_that("not_null and accepted_values", {
  t <- tbl(data.frame(a = c("x", "", " ", "y")))
  expect_identical(run_check(chk(type = "not_null", column = "a"), t)$failing_rows, 2L)
  r <- run_check(chk(type = "accepted_values", column = "a", values = list("x", "y")), t)
  expect_identical(c(r$failing_rows, r$status), c("2", "fail"))
})

test_that("range ignores missing values but not garbage", {
  r <- run_check(chk(type = "range", column = "a", min = 0, max = 10), tbl(data.frame(a = c("1", NA, "50", "abc"))))
  expect_identical(r$failing_rows, 2L)
})

test_that("relationship", {
  t <- list(t = data.frame(customer_id = c("C1", "C9")), customers = data.frame(customer_id = "C1"))
  expect_identical(run_check(chk(type = "relationship", column = "customer_id", to = "customers"), t)$failing_rows, 1L)
})

test_that("max_ratio is a share and only warns", {
  r <- run_check(chk(type = "max_ratio", column = "a", value = "unknown", max = 0.2, severity = "warn"),
                 tbl(data.frame(a = c("unknown", "x", "x", "x"))))
  expect_identical(list(r$failing_rows, r$observed, r$status), list(1L, 0.25, "warn"))
})

test_that("the tiny export passes every table check", {
  t <- tiny()
  results <- run_checks(CONTRACT, c(t$tables, list(raw_usage = t$raw$usage)),
                        only = c("customers", "invoices", "usage", "tickets", "raw_usage"))
  ids <- vapply(Filter(function(ch) ch$table != "snapshots", CONTRACT$checks), function(ch) ch$id, "")
  expect_identical(vapply(results, function(r) r$id, ""), ids)
  expect_true(all(vapply(results, function(r) r$status != "fail", logical(1))))
})

test_that("errors stop the run, warnings do not", {
  expect_true(raise_on_errors(list(list(id = "w", status = "warn"))))
  expect_error(raise_on_errors(list(list(id = "bad", status = "fail"))), "bad", class = "contract_error")
  expect_error(failing_rows(chk(type = "regex", column = "a"), tbl(data.frame(a = "x"))), "unknown check type")
})
