# M7 · Monitoring and retraining (contract/feature-spec.md §9), the v1.1 work after the model went live.
#
# Monitoring: the population stability index (PSI) of every feature and of the deployed score, each post-deployment
# snapshot against the training rows (bins = type-7 decile edges of the training values, duplicates dropped; bin of
# x = number of edges strictly below x; empty bins count as psi_floor), and the realised AUC, Brier, ECE and mean
# prediction on every labelled post-deployment month.
#
# Retraining: a challenger refitted on all labelled pre-deployment snapshots (the same tidymodels workflow), its
# intercept recalibrated on the most recent labelled month with glm(y ~ 1, offset = eta), then champion and challenger
# are compared on the holdout month. The challenger is promoted only if every check of the retraining gate passes.

POST_DEPLOYMENT <- c("recent", "holdout", "score")

psi_edges <- function(values, bins) sort(unique(quantile7(values, seq_len(bins - 1L) / bins)))

#' Share of values in each bin; findInterval(left.open = TRUE) counts the edges strictly below each value.
bin_shares <- function(values, edges) {
  idx <- findInterval(as.numeric(values), edges, left.open = TRUE)
  as.numeric(tabulate(idx + 1L, nbins = length(edges) + 1L)) / length(values)
}

psi <- function(reference, actual, floor) {
  e <- pmax(reference, floor)
  a <- pmax(actual, floor)
  sum((a - e) * log(a / e))
}

psi_status <- function(value, mon) {
  if (value >= mon$psi_drift) return("drift")
  if (value >= mon$psi_watch) "watch" else "stable"
}

profile <- function(values, bins) {
  edges <- psi_edges(values, bins)
  list(edges = as.list(edges), shares = as.list(bin_shares(values, edges)))
}

reference_profile <- function(rows, features, scores, bins) {
  list(bins = as.integer(bins), rows = nrow(rows),
       features = lapply(stats::setNames(features, features), function(f) profile(rows[[f]], bins)),
       score = profile(scores, bins))
}

#' Fairness on one evaluation month: max - min recall of the top-k call list across the fairness groups.
recall_gap <- function(frame, y, p, ev, missing) {
  y <- as.integer(y)
  c <- contacted(frame, p, ev$top_percent)
  f <- ev$fairness
  values <- as.character(frame[[f$dimension]])
  recalls <- c()
  for (v in sort(unique(values), method = "radix")) {
    m <- values == v
    if (v != missing && sum(y[m]) >= f$min_churners) recalls <- c(recalls, sum(c[m] & y[m] == 1) / sum(y[m]))
  }
  max(recalls) - min(recalls)
}

performance <- function(y, p) {
  cal <- calibration(y, p, 10L)
  list(auc = auc(y, p), brier = brier(y, p), ece = cal$ece, mean_pred = cal$mean_pred,
       observed_rate = cal$observed_rate)
}

num_text <- function(x) format(x)

monitor <- function(features, deployed, contract) {
  mon <- contract$monitoring
  names <- unlist(deployed$features)
  reference <- features[features$split == "train", , drop = FALSE]
  ref_p <- predict_logistic(deployed, reference)
  edges <- lapply(stats::setNames(names, names), function(f) psi_edges(reference[[f]], mon$psi_bins))
  shares <- lapply(names, function(f) bin_shares(reference[[f]], edges[[f]]))
  names(shares) <- names
  score_edges <- psi_edges(ref_p, mon$psi_bins)
  score_shares <- bin_shares(ref_p, score_edges)
  post <- features[features$split %in% POST_DEPLOYMENT, , drop = FALSE]
  drift <- list()
  performance_rows <- list()
  alerts <- character(0)
  for (snap in sort(unique(post$snapshot))) {
    g <- post[post$snapshot == snap, , drop = FALSE]
    p <- predict_logistic(deployed, g)
    per <- lapply(stats::setNames(names, names), function(f) {
      psi(shares[[f]], bin_shares(g[[f]], edges[[f]]), mon$psi_floor)
    })
    status <- vapply(per, psi_status, character(1), mon = mon)
    score_psi <- psi(score_shares, bin_shares(p, score_edges), mon$psi_floor)
    drift[[length(drift) + 1]] <- list(
      snapshot = snap, split = g$split[1], rows = nrow(g), score_psi = score_psi,
      score_status = psi_status(score_psi, mon), feature_psi = per,
      features_watch = as.list(names[status == "watch"]), features_drift = as.list(names[status == "drift"])
    )
    for (f in names[status == "drift"]) alerts <- c(alerts, sprintf("%s: %s drifted (PSI %.3f)", snap, f, per[[f]]))
    if (!anyNA(g$churned)) {
      m <- performance(as.integer(g$churned), p)
      own <- character(0)
      if (m$ece > mon$alert_max_ece) own <- c(own, sprintf("ECE %.3f > %s", m$ece, num_text(mon$alert_max_ece)))
      if (abs(m$mean_pred - m$observed_rate) > mon$alert_max_mean_gap) {
        own <- c(own, sprintf("mean predicted %.3f vs observed %.3f", m$mean_pred, m$observed_rate))
      }
      if (m$auc < mon$alert_min_auc) own <- c(own, sprintf("AUC %.3f < %s", m$auc, num_text(mon$alert_min_auc)))
      performance_rows[[length(performance_rows) + 1]] <- c(list(snapshot = snap, split = g$split[1], rows = nrow(g)),
                                                            m, list(alerts = as.list(own)))
      alerts <- c(alerts, if (length(own)) paste0(snap, ": ", own) else character(0))
    }
  }
  any_perf <- any(vapply(performance_rows, function(r) length(r$alerts) > 0, logical(1)))
  list(
    deployed_model = list(path = mon$deployed_model, model_version = deployed$model_version,
                          trained_by_track = deployed$generator$track),
    reference = list(split = "train", rows = nrow(reference)),
    drift = drift,
    performance = performance_rows,
    alerts = as.list(alerts),
    status = if (any_perf) "retrain" else if (length(alerts)) "watch" else "ok"
  )
}

#' The intercept shift d with sum(plogis(eta + d)) = sum(y): an intercept-only glm with the old score as offset.
calibration_offset <- function(eta, y) {
  fit <- stats::glm(y ~ 1, offset = eta, family = stats::binomial(),
                    control = stats::glm.control(epsilon = 1e-14, maxit = 100))
  unname(stats::coef(fit)[[1]])
}

retrain <- function(features, deployed, contract) {
  rt <- contract$retraining
  ev <- contract$evaluation
  names <- unlist(deployed$features)
  refit <- features[features$split %in% unlist(rt$refit_splits), , drop = FALSE]
  calib <- features[features$split == rt$calibrate_on, , drop = FALSE]
  hold <- features[features$split == rt$decide_on, , drop = FALSE]
  rownames(refit) <- NULL
  rownames(hold) <- NULL
  fit <- fit_logistic(refit[names], as.integer(refit$churned))
  offset <- calibration_offset(linear_predictor(fit, calib), as.integer(calib$churned))
  challenger <- list(intercept = fit$intercept + offset, coefficients = fit$coefficients)
  y <- as.integer(hold$churned)
  missing <- contract$cleaning$missing_label
  results <- lapply(list(champion = deployed, challenger = challenger), function(model) {
    p <- predict_logistic(model, hold)
    c(score_metrics(hold, y, p, ev),
      list(mean_pred = mean(p), observed_rate = mean(y), recall_gap = recall_gap(hold, y, p, ev, missing)))
  })
  ch <- results$champion
  cc <- results$challenger
  checks <- list(
    list(id = "auc_not_worse", value = cc$auc, threshold = ch$auc - rt$max_auc_drop,
         passed = cc$auc >= ch$auc - rt$max_auc_drop),
    list(id = "brier_improves", value = cc$brier, threshold = ch$brier, passed = cc$brier < ch$brier),
    list(id = "ece", value = cc$ece, threshold = rt$max_ece, passed = cc$ece <= rt$max_ece),
    list(id = "recall_gap", value = cc$recall_gap, threshold = rt$max_recall_gap,
         passed = cc$recall_gap <= rt$max_recall_gap)
  )
  passed <- all(vapply(checks, function(x) isTRUE(x$passed), logical(1)))
  list(
    fit = challenger,
    refit_rows = refit,
    calibration_rows = calib,
    calibration_scores = predict_logistic(challenger, calib),
    section = list(
      challenger = list(features = as.list(names), refit_snapshots = as.list(sort(unique(refit$snapshot))),
                        refit_rows = nrow(refit), calibration_snapshot = calib$snapshot[1],
                        calibration_offset = offset, intercept = challenger$intercept,
                        coefficients = challenger$coefficients),
      holdout = list(snapshot = hold$snapshot[1], rows = nrow(hold), churn_rate = mean(y)),
      champion_holdout = ch,
      challenger_holdout = cc,
      gate = list(checks = checks, passed = passed),
      decision = if (passed) "promote" else "keep"
    )
  )
}
