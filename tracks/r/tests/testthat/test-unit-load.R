skip_if_pending("test-unit-load.R")

test_that("every file is read as text, empty cells stay empty", {
  raw <- load_raw(TINY, CONTRACT)
  expect_equal(lapply(raw, nrow), EXPECTED$raw_rows[names(raw)])
  expect_true(all(vapply(raw, function(df) all(vapply(df, is.character, logical(1))), logical(1))))
  expect_identical(raw$customers$acquisition_channel[3], "")
})

test_that("columns come in contract order", {
  raw <- load_raw(TINY, CONTRACT)
  for (name in names(CONTRACT$files)) expect_identical(names(raw[[name]]), unlist(CONTRACT$files[[name]]$columns))
})

test_that("a missing file is a contract error", {
  path <- export_copy()
  file.remove(file.path(path, "usage.csv"))
  expect_error(load_raw(path, CONTRACT), "usage\\.csv", class = "contract_error")
})

test_that("a missing column is a contract error", {
  path <- export_copy()
  f <- file.path(path, "tickets.csv")
  text <- readLines(f, encoding = "UTF-8")
  text[1] <- sub("resolved_at", "closed_at", text[1], fixed = TRUE)
  writeLines(text, f, useBytes = TRUE)
  expect_error(load_raw(path, CONTRACT), "resolved_at", class = "contract_error")
})

test_that("export metadata", {
  expect_identical(load_export(TINY)$export, "2026-03")
  path <- export_copy()
  file.remove(file.path(path, "export.json"))
  expect_error(load_export(path), class = "contract_error")
})
