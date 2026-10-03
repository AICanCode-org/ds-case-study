skip_if_pending("test-data-golden.R")
# Golden metrics: the whole metrics.json on the real export equals the reference all tracks agreed on.
# Fix the cause in the code, never the golden file (scripts/parity.py prints the JSON paths that differ).

test_that("the metrics equal the golden file", {
  golden <- jsonlite::read_json(file.path(CONTRACT_DIR, "golden", "metrics-2026-05.json"))
  problems <- json_diff(golden, as_json_lists(real_result()$metrics))
  expect_null(problems)
})

test_that("the model artefact equals the golden one", {
  golden <- jsonlite::read_json(file.path(CONTRACT_DIR, "golden", "model-2026-05.json"))
  expect_null(json_diff(golden, as_json_lists(real_result()$artefact)))
})

test_that("write_outputs writes the four files", {
  out <- tempfile("out")
  write_outputs(real_result(), out)
  expect_setequal(list.files(out), c("experiments.jsonl", "features.csv", "metrics.json", "model.json"))
  lines <- lapply(readLines(file.path(out, "experiments.jsonl")), jsonlite::fromJSON)
  expect_identical(vapply(lines, function(x) x$id, ""), c("B0", "B1", "E1", "E2"))
  expect_identical(sum(vapply(lines, function(x) x$champion, logical(1))), 1L)
  header <- strsplit(readLines(file.path(out, "features.csv"), n = 1), ",")[[1]]
  expect_identical(header[1:5], c("customer_id", "snapshot", "split", "fold", "churned"))
})
