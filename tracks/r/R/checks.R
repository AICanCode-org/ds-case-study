# M2 · The contract checks (contract/data-contract.yaml `checks`): one result per check, in contract order.
# A failing check with severity `error` stops the run (exit code 3): a model trained on a broken export is worse
# than no model.

check_values <- function(table, column) {
  # TODO(M2) check_values: the column(s) a check looks at (a list of columns means a composite key). Spec:
  # contract/feature-spec.md §2 and contract/data-contract.yaml `checks`; tests: checks.
  stop("TODO(M2) check_values: see the comment above")
}

#' c(failing rows, rows checked) for one check.
failing_rows <- function(check, tables) {
  # TODO(M2) failing_rows: one contract check -> (failing rows, checked rows), by type: unique, not_null,
  # accepted_values, range, relationship, max_ratio. Spec: contract/feature-spec.md §2 and
  # contract/data-contract.yaml `checks`; tests: checks.
  stop("TODO(M2) failing_rows: see the comment above")
}

run_check <- function(check, tables) {
  # TODO(M2) run_check: one check -> {id, severity, status, failing_rows, observed}; status pass, else warn/fail
  # by severity. Spec: contract/feature-spec.md §2 and contract/data-contract.yaml `checks`; tests: checks.
  stop("TODO(M2) run_check: see the comment above")
}

run_checks <- function(contract, tables, only) {
  # TODO(M2) run_checks: every check of contract/data-contract.yaml for the given tables, in contract order.
  # Spec: contract/feature-spec.md §2 and contract/data-contract.yaml `checks`; tests: checks.
  stop("TODO(M2) run_checks: see the comment above")
}

raise_on_errors <- function(results) {
  # TODO(M2) raise_on_errors: a failing `error` check stops the run with a contract error (exit 3): no model is
  # better than a model trained on a broken export. Spec: contract/feature-spec.md §2 and
  # contract/data-contract.yaml `checks`; tests: checks.
  stop("TODO(M2) raise_on_errors: see the comment above")
}
