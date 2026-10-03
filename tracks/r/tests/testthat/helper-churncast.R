# ---------------------------------------------------------------------------
# PENDING test files describe behaviour you have not built yet, so they are skipped.
# When you start a milestone, delete its line here, watch the tests fail (red),
# implement until they pass (green). See docs/phase-3.
# ---------------------------------------------------------------------------
PENDING <- c()

skip_if_pending <- function(file) {
  if (file %in% names(PENDING)) skip(sprintf("PENDING (%s) - see tests/testthat/helper-churncast.R", PENDING[[file]]))
}

# covr runs the tests from a temporary copy of the package, so it passes the repo path explicitly
REPO <- Sys.getenv("CHURNCAST_REPO", normalizePath(test_path("..", "..", "..", "..")))
Sys.setenv(CONTRACT_PATH = file.path(REPO, "contract", "data-contract.yaml"))
CONTRACT_DIR <- file.path(REPO, "contract")
TINY <- file.path(CONTRACT_DIR, "fixtures", "tiny")
EXPORT_V10 <- file.path(REPO, "data", "raw", "2026-05")
EXPORT_V11 <- file.path(REPO, "data", "raw", "2026-07")
EXPECTED <- jsonlite::read_json(file.path(CONTRACT_DIR, "fixtures", "tiny-expected.json"))
CASES <- jsonlite::read_json(file.path(CONTRACT_DIR, "fixtures", "metric-cases.json"))
CONTRACT <- load_contract()

#' The shared contract with the tiny export's snapshots (see tiny-expected.json).
tiny_contract <- function() {
  contract <- CONTRACT
  for (k in names(EXPECTED$snapshots)) contract$snapshots[[k]] <- EXPECTED$snapshots[[k]]
  contract
}

#' The hand-made tiny export, loaded and cleaned.
tiny <- function() {
  contract <- tiny_contract()
  raw <- load_raw(TINY, contract)
  c(list(raw = raw), clean_tables(raw, contract))
}

#' A writable copy of an export folder, to corrupt on purpose.
export_copy <- function(source = TINY) {
  target <- file.path(tempfile("export"), basename(source))
  dir.create(target, recursive = TRUE)
  file.copy(list.files(source, full.names = TRUE), target)
  target
}

append_line <- function(path, line) cat(line, "\n", file = path, sep = "", append = TRUE)

nums <- function(x) vapply(x, function(v) if (is.null(v)) NA_real_ else as.numeric(v), 0)

#' The whole pipeline on the latest export, 2026-07, computed once per test run (about 12 s): training, evaluation,
#' then monitoring of the deployed v1.0 model and the champion/challenger retraining (Phase 7).
CACHE <- new.env()
real_result <- function() {
  if (is.null(CACHE$result)) CACHE$result <- analyse(EXPORT_V11, CONTRACT)
  CACHE$result
}

#' The same code on the 2026-05 export: it must still reproduce the v1.0 release (backward compatibility).
result_v10 <- function() {
  if (is.null(CACHE$v10)) CACHE$v10 <- analyse(EXPORT_V10, CONTRACT)
  CACHE$v10
}

#' A result as the same JSON text the CLI writes, read back as plain lists.
as_json_lists <- function(x) jsonlite::fromJSON(to_json(x), simplifyVector = FALSE)

BACKCOMPAT_IGNORE <- c("$/schema_version", "$/dataset/contract_version", "$/training/contract_version",
                       "$/model_version")

#' The same comparison as scripts/parity.py: integers and text exactly, other numbers to 1e-6 abs + 1e-6 rel.
#' subset = TRUE is parity.py --backcompat: `a` is the older file, extra fields in `b` are allowed.
json_diff <- function(a, b, path = "$", subset = FALSE) {
  if (subset && path %in% BACKCOMPAT_IGNORE) return(NULL)
  if (is.list(a) && is.list(b)) {
    if (is.null(names(a))) {
      if (length(a) != length(b)) return(path)
      keys <- seq_along(a)
    } else {
      keys <- setdiff(names(a), "generator")
      other <- setdiff(names(b), "generator")
      if (if (subset) !all(keys %in% other) else !setequal(keys, other)) return(path)
    }
    return(unlist(lapply(keys, function(k) json_diff(a[[k]], b[[k]], paste0(path, "/", k), subset))))
  }
  if (is.numeric(a) && is.numeric(b)) {
    if (abs(a - b) <= 1e-6 + 1e-6 * abs(a)) return(NULL) else return(path)
  }
  if (identical(a, b)) NULL else path
}

#' Run the CLI with its stderr captured; returns the exit code with the captured text as attribute "stderr".
run_cli <- function(args) {
  code <- NULL
  err <- utils::capture.output(code <- main(args), type = "message")
  structure(code, stderr = paste(err, collapse = "\n"))
}
