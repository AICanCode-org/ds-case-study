skip_if_pending("test-data-contract-violations.R")
# A broken export must stop the run with exit code 3, never train a model on it.

run_broken <- function(edit) {
  path <- export_copy(EXPORT_V10)
  edit(path)
  run_cli(c("run", "--data", path, "--out", tempfile()))
}

expect_contract_error <- function(edit, check_id) {
  expect_error(analyse(local({
    path <- export_copy(EXPORT_V10)
    edit(path)
    path
  }), CONTRACT), check_id, class = "contract_error")
}

test_that("an unknown plan", {
  line <- "INV9999999,C00010,2026-05,charge,platinum,5999,0,paid"
  expect_contract_error(function(p) append_line(file.path(p, "invoices.csv"), line), "invoices.plan.accepted")
})

test_that("a reused invoice id", {
  line <- "INV0000001,C00010,2026-05,charge,basic,2499,0,paid"
  expect_contract_error(function(p) append_line(file.path(p, "invoices.csv"), line), "invoices.invoice_id.unique")
})

test_that("a broken billing export with no renewals", {
  expect_contract_error(function(p) {
    f <- file.path(p, "invoices.csv")
    lines <- readLines(f, encoding = "UTF-8")
    writeLines(lines[!grepl(",2026-04,", lines, fixed = TRUE)], f, useBytes = TRUE)
  }, "snapshots.churn_rate.range")
})

test_that("an impossible meal count exits 3 from the CLI", {
  code <- run_broken(function(p) append_line(file.path(p, "usage.csv"), "C00010,2026-06,99,0,0,0,0"))
  expect_identical(as.integer(code), 3L)
  expect_match(attr(code, "stderr"), "usage.meals_ordered.range", fixed = TRUE)
})
