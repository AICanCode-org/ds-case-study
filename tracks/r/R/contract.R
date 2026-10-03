# The shared data contract (contract/data-contract.yaml): one file, read by every track.

#' The track folder: works from run.R, the tests and covr's temporary copy.
track_root <- function() {
  root <- Sys.getenv("CHURNCAST_R_TRACK", "")
  if (nzchar(root)) return(root)
  normalizePath(".")
}

contract_path <- function() {
  env <- Sys.getenv("CONTRACT_PATH", "")
  if (nzchar(env)) return(env)
  file.path(track_root(), "..", "..", "contract", "data-contract.yaml")
}

load_contract <- function(path = NULL) {
  path <- if (is.null(path)) contract_path() else path
  yaml::read_yaml(path)
}

feature_names <- function(contract, core_only = FALSE) {
  keep <- vapply(contract$features, function(f) isTRUE(f$core) || !core_only, logical(1))
  vapply(contract$features[keep], function(f) f$name, character(1))
}

#' The export breaks the data contract: the run must stop (exit code 3).
contract_error <- function(message) {
  stop(structure(class = c("contract_error", "error", "condition"), list(message = message, call = NULL)))
}
