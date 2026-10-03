skip_if_pending("test-unit-cli.R")

test_that("usage errors exit 2", {
  for (args in list(character(0), c("run", "--bogus", "x"), c("run", "--out", "x"))) {
    code <- run_cli(args)
    expect_identical(as.integer(code), 2L)
    expect_match(attr(code, "stderr"), "usage")
  }
})

test_that("a missing export is an I/O error", {
  code <- run_cli(c("run", "--data", file.path(tempdir(), "nope"), "--out", tempfile()))
  expect_identical(as.integer(code), 2L)
  expect_match(attr(code, "stderr"), "no export folder")
})

test_that("a broken contract value exits 3", {
  path <- export_copy()
  append_line(file.path(path, "customers.csv"), "C00007,2026-01-05,Mumbai,organic,25-34,")
  code <- run_cli(c("run", "--data", path, "--out", tempfile()))
  expect_identical(as.integer(code), 3L)
  expect_match(attr(code, "stderr"), "customers.city.accepted", fixed = TRUE)
})

test_that("an unreadable contract file exits 2", {
  code <- suppressWarnings(run_cli(c("run", "--data", TINY, "--out", tempfile(), "--contract", tempfile())))
  expect_identical(as.integer(code), 2L)
})
