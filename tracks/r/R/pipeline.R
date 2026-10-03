# M5 · The whole run: raw export -> checks -> features -> experiments -> champion -> evaluation -> artefacts.
#
# out/features.csv       one row per customer and snapshot (the parity check compares it across tracks)
# out/metrics.json       everything the model card, the tests and CI read (schema: contract/metrics.schema.json)
# out/model.json         the champion, language-neutral (schema: contract/model.schema.json)
# out/experiments.jsonl  the experiment log: one line per experiment

TRACK <- "r"
VERSION <- "1.0.0"

experiment_features <- function(exp, contract) {
  # TODO(M5) experiment_features: the features of a logistic experiment (core or all); none for the baselines.
  # Spec: contract/feature-spec.md §5-§7 and contract/metrics.schema.json; tests: cli.
  stop("TODO(M5) experiment_features: see the comment above")
}

fit_experiment <- function(exp, contract, rows) {
  # TODO(M5) fit_experiment: fit one experiment (prior, rule or logistic) on some rows. Spec:
  # contract/feature-spec.md §5-§7 and contract/metrics.schema.json; tests: cli.
  stop("TODO(M5) fit_experiment: see the comment above")
}

predict_experiment <- function(exp, contract, fit, rows) {
  # TODO(M5) predict_experiment: predict one fitted experiment on some rows. Spec: contract/feature-spec.md
  # §5-§7 and contract/metrics.schema.json; tests: cli.
  stop("TODO(M5) predict_experiment: see the comment above")
}

#' 5-fold grouped cross-validation over the contract folds (an rsample manual_rset).
cross_validate <- function(exp, contract, train) {
  # TODO(M5) cross_validate: 5-fold grouped CV on the training rows: fit on the other folds, score the held-out
  # fold; mean and sample SD of the fold AUCs. Spec: contract/feature-spec.md §5-§7 and
  # contract/metrics.schema.json; tests: cli.
  stop("TODO(M5) cross_validate: see the comment above")
}

choose_champion <- function(experiments, contract) {
  # TODO(M5) choose_champion: the bigger logistic experiment only if its mean CV AUC beats the simpler one by
  # the contract's margin; the reason in words. Spec: contract/feature-spec.md §5-§7 and
  # contract/metrics.schema.json; tests: cli.
  stop("TODO(M5) choose_champion: see the comment above")
}

analyse <- function(data_dir, contract = load_contract()) {
  # TODO(M5) analyse: the whole run: load, clean, checks, features, experiments (CV, then the test months once),
  # champion, evaluation, gate, artefact. Returns metrics, artefact and features. Spec: contract/feature-spec.md
  # §5-§7 and contract/metrics.schema.json; tests: cli.
  stop("TODO(M5) analyse: see the comment above")
}

to_json <- function(x) {
  jsonlite::toJSON(x, auto_unbox = TRUE, digits = NA, null = "null", na = "null", pretty = TRUE)
}

write_outputs <- function(result, out_dir) {
  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  f <- result$features
  readr::write_csv(f, file.path(out_dir, "features.csv"), na = "")
  writeLines(to_json(result$metrics), file.path(out_dir, "metrics.json"), useBytes = TRUE)
  writeLines(to_json(result$artefact), file.path(out_dir, "model.json"), useBytes = TRUE)
  m <- result$metrics
  lines <- vapply(m$experiments, function(e) {
    line <- list(run = list(export = m$dataset$export, contract_version = m$dataset$contract_version, track = TRACK,
                            version = VERSION),
                 id = e$id, name = e$name, features = e$features, cv_auc_mean = e$cv$auc_mean,
                 cv_auc_sd = e$cv$auc_sd, test_auc = e$test$auc, test_brier = e$test$brier,
                 champion = e$id == m$champion$experiment)
    as.character(jsonlite::toJSON(line, auto_unbox = TRUE, digits = NA, null = "null", na = "null"))
  }, character(1))
  writeLines(lines, file.path(out_dir, "experiments.jsonl"), useBytes = TRUE)
  invisible(out_dir)
}

usage <- function() {
  cat("usage: Rscript run.R run --data <export folder> [--out out] [--contract path]\n", file = stderr())
  2L
}

#' CLI. Exit codes: 0 ok (even if the gate fails: CI enforces it), 2 usage or I/O error, 3 contract error.
main <- function(args = commandArgs(trailingOnly = TRUE)) {
  if (length(args) < 1 || args[1] != "run") return(usage())
  opts <- list(out = "out", contract = NULL, data = NULL)
  rest <- args[-1]
  while (length(rest) >= 2) {
    key <- sub("^--", "", rest[1])
    if (!key %in% names(opts)) return(usage())
    opts[[key]] <- rest[2]
    rest <- rest[-(1:2)]
  }
  if (length(rest) > 0 || is.null(opts$data)) return(usage())
  if (!dir.exists(opts$data)) {
    cat(sprintf("error: no export folder at %s\n", opts$data), file = stderr())
    return(2L)
  }
  outcome <- tryCatch({
    contract <- load_contract(opts$contract)
    result <- analyse(opts$data, contract)
    write_outputs(result, opts$out)
    result
  }, contract_error = function(e) {
    cat(sprintf("contract error: %s\n", conditionMessage(e)), file = stderr())
    3L
  }, error = function(e) {
    cat(sprintf("error: %s\n", conditionMessage(e)), file = stderr())
    2L
  })
  if (is.integer(outcome)) return(outcome)
  m <- outcome$metrics
  cat(sprintf("champion %s: test AUC %.3f, Brier %.4f, ECE %.4f, gate %s -> %s/\n", m$champion$experiment, m$test$auc,
              m$test$brier, m$test$ece, if (m$gate$passed) "PASSED" else "FAILED", opts$out))
  0L
}
