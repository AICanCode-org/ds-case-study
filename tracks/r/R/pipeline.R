# M5 · The whole run: raw export -> checks -> features -> experiments -> champion -> evaluation -> artefacts.
#
# out/features.csv       one row per customer and snapshot (the parity check compares it across tracks)
# out/metrics.json       everything the model card, the tests and CI read (schema: contract/metrics.schema.json)
# out/model.json         the champion, language-neutral (schema: contract/model.schema.json)
# out/experiments.jsonl  the experiment log: one line per experiment

TRACK <- "r"
VERSION <- "1.1.0"
ARTEFACT_TEST_KEYS <- c("auc", "average_precision", "brier", "ece", "precision_at_top", "recall_at_top")

experiment_features <- function(exp, contract) {
  if (exp$kind != "logistic") return(character(0))
  feature_names(contract, core_only = exp$features == "core")
}

fit_experiment <- function(exp, contract, rows) {
  y <- as.integer(rows$churned)
  switch(exp$kind,
    prior = fit_prior(y),
    rule = fit_rule(rows, y, contract$rule_baseline),
    logistic = fit_logistic(rows[experiment_features(exp, contract)], y)
  )
}

predict_experiment <- function(exp, contract, fit, rows) {
  switch(exp$kind,
    prior = predict_prior(fit, rows),
    rule = predict_rule(fit, rows, contract$rule_baseline),
    logistic = predict_logistic(fit, rows)
  )
}

#' 5-fold grouped cross-validation over the contract folds (an rsample manual_rset).
cross_validate <- function(exp, contract, train) {
  rset <- contract_folds(train, contract$snapshots$folds)
  folds <- lapply(seq_along(rset$splits), function(i) {
    split <- rset$splits[[i]]
    fit_rows <- rsample::analysis(split)
    val <- rsample::assessment(split)
    p <- predict_experiment(exp, contract, fit_experiment(exp, contract, fit_rows), val)
    y <- as.integer(val$churned)
    list(fold = i - 1L, rows = nrow(val), auc = auc(y, p), brier = brier(y, p), log_loss = log_loss(y, p))
  })
  a <- vapply(folds, function(f) f$auc, numeric(1))
  list(auc_mean = mean(a), auc_sd = stats::sd(a),
       brier_mean = mean(vapply(folds, function(f) f$brier, numeric(1))),
       log_loss_mean = mean(vapply(folds, function(f) f$log_loss, numeric(1))),
       folds = folds)
}

choose_champion <- function(experiments, contract) {
  logistic <- Filter(function(e) e$kind == "logistic", experiments)
  simple <- logistic[[1]]
  bigger <- logistic[[length(logistic)]]
  gain <- bigger$cv$auc_mean - simple$cv$auc_mean
  need <- contract$champion$min_cv_auc_gain_for_complexity
  if (gain >= need) {
    return(list(id = bigger$id, reason = sprintf("%s beats %s by %.4f mean CV AUC (>= %s)", bigger$id, simple$id,
                                                  gain, format(need))))
  }
  list(id = simple$id, reason = sprintf("%s gains only %.4f mean CV AUC (< %s): keep the simpler %s", bigger$id, gain,
                                        format(need), simple$id))
}

#' The deployed model (1.1): $DEPLOYED_MODEL_PATH, or the contract's path relative to the repository root (the folder
#' that holds contract/).
load_deployed <- function(contract) {
  path <- Sys.getenv("DEPLOYED_MODEL_PATH", "")
  if (!nzchar(path)) path <- file.path(dirname(contract_path()), "..", contract$monitoring$deployed_model)
  if (!file.exists(path)) stop(sprintf("deployed model not found: %s", path))
  jsonlite::read_json(path, simplifyVector = FALSE)
}

analyse <- function(data_dir, contract = load_contract(), deployed = NULL) {
  export <- load_export(data_dir)
  raw <- load_raw(data_dir, contract)
  cleaned <- clean_tables(raw, contract)
  tables <- cleaned$tables
  checks <- run_checks(contract, c(tables, list(raw_usage = raw$usage)),
                       only = c("customers", "invoices", "usage", "tickets", "raw_usage"))
  raise_on_errors(checks)
  export_month <- month_index(export$export)
  features <- build_features(tables, contract, export_month)
  summary <- snapshot_summary(features)
  snap_table <- data.frame(rows = vapply(summary, function(s) s$rows, numeric(1)),
                           churn_rate = vapply(summary, function(s) if (is.null(s$churn_rate)) NA else s$churn_rate,
                                               numeric(1)))
  snap_checks <- run_checks(contract, list(snapshots = snap_table), only = "snapshots")
  checks <- c(checks, snap_checks)
  raise_on_errors(snap_checks)
  names <- feature_names(contract)
  ev <- contract$evaluation
  train <- features[features$split == "train", , drop = FALSE]
  test <- features[features$split == "test", , drop = FALSE]
  rownames(train) <- NULL
  rownames(test) <- NULL
  y_test <- as.integer(test$churned)

  experiments <- list()
  fits <- list()
  preds <- list()
  for (exp in contract$experiments) {
    cv <- cross_validate(exp, contract, train)
    fits[[exp$id]] <- fit_experiment(exp, contract, train)
    preds[[exp$id]] <- predict_experiment(exp, contract, fits[[exp$id]], test)
    experiments[[length(experiments) + 1]] <- list(
      id = exp$id, name = exp$name, kind = exp$kind, features = as.list(experiment_features(exp, contract)),
      cv = cv, test = score_metrics(test, y_test, preds[[exp$id]], ev)
    )
  }
  champion <- choose_champion(experiments, contract)
  champ <- Filter(function(e) e$id == champion$id, experiments)[[1]]
  fit <- fits[[champion$id]]
  p <- preds[[champion$id]]
  used <- unlist(champ$features)
  means <- lapply(stats::setNames(used, used), function(f) mean(train[[f]]))
  sds <- lapply(stats::setNames(used, used), function(f) sqrt(mean((train[[f]] - mean(train[[f]]))^2)))
  threshold <- quantile7(predict_logistic(fit, train), 0.9)
  test_m <- champ$test
  slice_rows <- slices(test, y_test, p, ev)
  fair <- fairness(slice_rows, ev, contract$cleaning$missing_label)
  reasons <- tables$customers$cancellation_reason[match(train$customer_id, tables$customers$customer_id)]
  probe <- as.integer(!is.na(reasons) & trimws(reasons) != "")
  leak <- leakage_scan(train, names, probe, ev$leakage_max_single_feature_auc)
  by_id <- stats::setNames(lapply(experiments, function(e) e$test), vapply(experiments, function(e) e$id, ""))
  verdict <- gate(test_m, by_id$B1, by_id$B0, fair, leak, contract$gate)
  training <- list(export = export$export, contract_version = contract$contract_version,
                   snapshots = as.list(unlist(contract$snapshots$train)), rows = nrow(train),
                   churners = sum(train$churned))
  bins <- if (is.null(contract$monitoring$psi_bins)) 10L else contract$monitoring$psi_bins
  artefact <- build_artefact(fit, champion$id, used, means, threshold, mean(train$churned), training,
                             test_m[ARTEFACT_TEST_KEYS], VERSION, TRACK,
                             reference_profile(train, used, predict_logistic(fit, train), bins),
                             list(parent_model_version = NULL,
                                  trained_on = as.list(unlist(contract$snapshots$train))))
  post <- list()
  labelled <- unique(features$split[!is.na(features$churned)])
  if (!is.null(contract$monitoring) && all(c("recent", "holdout") %in% labelled)) {
    if (is.null(deployed)) deployed <- load_deployed(contract)
    post$monitoring <- monitor(features, deployed, contract)
    r <- retrain(features, deployed, contract)
    post$retraining <- r$section
    sec <- r$section
    refit <- r$refit_rows
    artefact <- build_artefact(
      r$fit, champion$id, used, lapply(stats::setNames(used, used), function(f) mean(refit[[f]])),
      quantile7(r$calibration_scores, 0.9), mean(as.integer(r$calibration_rows$churned)),
      list(export = export$export, contract_version = contract$contract_version,
           snapshots = sec$challenger$refit_snapshots, rows = nrow(refit), churners = sum(refit$churned)),
      sec$challenger_holdout[ARTEFACT_TEST_KEYS], VERSION, TRACK,
      reference_profile(refit, used, predict_logistic(r$fit, refit), bins),
      list(parent_model_version = deployed$model_version, refit_snapshots = sec$challenger$refit_snapshots,
           calibration_snapshot = sec$challenger$calibration_snapshot,
           calibration_offset = sec$challenger$calibration_offset, decided_on = sec$holdout$snapshot,
           decision = sec$decision)
    )
  }
  importance <- lapply(used, function(f) {
    list(feature = f, coefficient = fit$coefficients[[f]], sd = sds[[f]],
         standardised = fit$coefficients[[f]] * sds[[f]])
  })
  importance <- importance[order(-vapply(importance, function(r) abs(r$standardised), numeric(1)))]
  fold_ids <- seq_len(contract$snapshots$folds) - 1L
  metrics <- list(
    schema_version = "1.1",
    generator = list(track = TRACK, version = VERSION),
    dataset = list(export = export$export, period_end = export$period_end,
                   contract_version = contract$contract_version),
    data_quality = list(raw_rows = lapply(raw, nrow), clean_rows = lapply(tables, nrow), issues = cleaned$issues,
                        checks = checks),
    snapshots = summary,
    split = list(
      train_snapshots = as.list(unlist(contract$snapshots$train)),
      test_snapshots = as.list(unlist(contract$snapshots$test)),
      train_rows = nrow(train), test_rows = nrow(test),
      train_churn_rate = mean(train$churned), test_churn_rate = mean(y_test),
      folds = lapply(fold_ids, function(k) {
        m <- train$fold == k
        list(fold = k, rows = sum(m), customers = length(unique(train$customer_id[m])),
             churners = sum(train$churned[m]))
      }),
      customers_in_two_folds = sum(tapply(train$fold, train$customer_id, function(f) length(unique(f))) > 1)
    ),
    leakage = leak,
    experiments = experiments,
    champion = list(experiment = champion$id, reason = champion$reason, features = as.list(used),
                    intercept = fit$intercept, coefficients = fit$coefficients, feature_means = means,
                    importance = importance, high_risk_threshold = threshold),
    test = test_m,
    calibration = calibration(y_test, p, ev$calibration_bins),
    slices = slice_rows,
    fairness = fair,
    gate = verdict
  )
  metrics <- c(metrics, post)
  list(metrics = metrics, artefact = artefact, features = features)
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
