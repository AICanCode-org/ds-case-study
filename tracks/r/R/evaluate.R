# M4-M5 · Evaluation (contract/feature-spec.md §6): the metrics written out by hand so every track computes exactly
# the same number (tests compare the AUC with yardstick::roc_auc_vec), plus calibration, the retention-capacity
# view (top 10 % per month), slices, fairness, leakage and the gate.

EPS <- 1e-15

#' Area under the ROC curve = P(score of a churner > score of a stayer), ties count 1/2 (average ranks).
auc <- function(y, p) {
  # TODO(M4) auc: P(score of a churner > score of a stayer), ties count 1/2 (average ranks); null with one class
  # only. Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
  stop("TODO(M4) auc: see the comment above")
}

#' Sum over distinct thresholds (high to low) of (recall_k - recall_k-1) * precision_k.
average_precision <- function(y, p) {
  # TODO(M4) average_precision: sum over distinct scores, high to low, of (recall_k - recall_k-1) * precision_k.
  # Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
  stop("TODO(M4) average_precision: see the comment above")
}

brier <- function(y, p) {
  # TODO(M4) brier: mean squared error of the probabilities. Spec: contract/feature-spec.md §6 (+
  # contract/fixtures/metric-cases.json); tests: metrics.
  stop("TODO(M4) brier: see the comment above")
}

log_loss <- function(y, p) {
  # TODO(M4) log_loss: clip p to [1e-15, 1 - 1e-15] first. Spec: contract/feature-spec.md §6 (+
  # contract/fixtures/metric-cases.json); tests: metrics.
  stop("TODO(M4) log_loss: see the comment above")
}

calibration <- function(y, p, bins) {
  # TODO(M4) calibration: 10 equal-width bins ([k/10, (k+1)/10), p = 1 in the last); ECE = sum n_b / n * |mean p
  # - observed|. Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
  stop("TODO(M4) calibration: see the comment above")
}

#' ceil(n * percent / 100) in integers: no floating-point surprise.
top_k <- function(n, percent) (as.integer(n) * as.integer(percent) + 99L) %/% 100L

#' TRUE for the top `percent` % of each snapshot by risk (ties: lower customer_id first).
contacted <- function(frame, p, percent) {
  # TODO(M4) contacted: the top k of EACH snapshot by risk; ties: the lower customer_id first. Spec:
  # contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
  stop("TODO(M4) contacted: see the comment above")
}

capacity_metrics <- function(frame, y, p, ev) {
  # TODO(M4) capacity_metrics: precision, recall and lift of the call list, and the net value per month
  # (contract's cost, save rate and value months). Spec: contract/feature-spec.md §6 (+
  # contract/fixtures/metric-cases.json); tests: metrics.
  stop("TODO(M4) capacity_metrics: see the comment above")
}

score_metrics <- function(frame, y, p, ev) {
  # TODO(M4) score_metrics: every test metric of one experiment: AUC, AP, Brier, log loss, ECE + the capacity
  # metrics. Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
  stop("TODO(M4) score_metrics: see the comment above")
}

slices <- function(frame, y, p, ev) {
  # TODO(M4) slices: per slice value: rows, churners, mean prediction, AUC only with enough rows and churners,
  # recall of the call list. Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests:
  # metrics.
  stop("TODO(M4) slices: see the comment above")
}

fairness <- function(slice_rows, ev, missing) {
  # TODO(M4) fairness: recall gap of the call list across age bands with >= min_churners (never 'unknown').
  # Spec: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
  stop("TODO(M4) fairness: see the comment above")
}

#' Single-feature AUC (folded to >= 0.5) of every model feature on the training rows, and of the leaky probe.
leakage_scan <- function(train, features, probe, limit) {
  # TODO(M4) leakage_scan: single-feature AUC (folded to >= 0.5) of every model feature on the training rows,
  # and of the cancellation_reason probe (it should look suspiciously good: that is why it is banned). Spec:
  # contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: metrics.
  stop("TODO(M4) leakage_scan: see the comment above")
}

gate <- function(test, rule_test, prior_test, fair, leak, g) {
  # TODO(M4) gate: the six release checks of the contract, in order. Spec: contract/feature-spec.md §6 (+
  # contract/fixtures/metric-cases.json); tests: metrics.
  stop("TODO(M4) gate: see the comment above")
}

#' Type-7 quantile (R's and numpy's default): linear interpolation between order statistics.
quantile7 <- function(values, q) unname(stats::quantile(as.numeric(values), q, type = 7))
