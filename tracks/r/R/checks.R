# M2 · The contract checks (contract/data-contract.yaml `checks`): one result per check, in contract order.
# A failing check with severity `error` stops the run (exit code 3): a model trained on a broken export is worse
# than no model.

check_values <- function(table, column) {
  if (length(column) > 1) return(do.call(paste, c(lapply(table[unlist(column)], as.character), sep = "|")))
  table[[column]]
}

#' c(failing rows, rows checked) for one check.
failing_rows <- function(check, tables) {
  table <- tables[[check$table]]
  kind <- check$type
  if (kind == "unique") {
    v <- check_values(table, check$column)
    return(c(sum(duplicated(v)), length(v)))
  }
  v <- table[[check$column]]
  switch(kind,
    not_null = c(sum(is.na(v) | trimws(as.character(v)) == ""), length(v)),
    accepted_values = c(sum(!(as.character(v) %in% as.character(unlist(check$values)))), length(v)),
    range = {
      known <- v[!is.na(v)]
      num <- suppressWarnings(as.numeric(known))
      c(sum(is.na(num) | num < check$min | num > check$max), length(known))
    },
    relationship = c(sum(!(v %in% tables[[check$to]]$customer_id)), length(v)),
    max_ratio = c(sum(as.character(v) == as.character(check$value)), length(v)),
    stop("unknown check type: ", kind)
  )
}

run_check <- function(check, tables) {
  counts <- failing_rows(check, tables)
  observed <- if (counts[2] > 0) counts[1] / counts[2] else 0
  ok <- if (check$type == "max_ratio") observed <= check$max else counts[1] == 0
  status <- if (ok) "pass" else if (check$severity == "error") "fail" else "warn"
  list(id = check$id, severity = check$severity, status = status, failing_rows = as.integer(counts[1]),
       observed = as.numeric(observed))
}

run_checks <- function(contract, tables, only) {
  keep <- Filter(function(ch) ch$table %in% only, contract$checks)
  lapply(keep, run_check, tables = tables)
}

raise_on_errors <- function(results) {
  failed <- vapply(Filter(function(r) r$status == "fail", results), function(r) r$id, character(1))
  if (length(failed) > 0) contract_error(paste0("contract check(s) failed: ", paste(failed, collapse = ", ")))
  invisible(TRUE)
}
