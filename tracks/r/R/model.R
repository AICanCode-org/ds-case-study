# M4 · Baselines and the logistic regression (contract/feature-spec.md §5), with tidymodels.
#
# The model is parsnip's logistic_reg() on the "glm" engine inside a workflow: unpenalised maximum likelihood, the
# same estimate scikit-learn's Newton-Cholesky solver finds in the Python track. glm's convergence tolerance is
# tightened (epsilon 1e-12) so the coefficients agree to far better than the parity tolerance.

logistic_spec <- function() {
  # TODO(M4) logistic_spec: parsnip::logistic_reg() with the glm engine; tighten glm.control(epsilon). Spec:
  # contract/feature-spec.md §5; tests: model.
  stop("TODO(M4) logistic_spec: see the comment above")
}

#' The outcome as a factor with the event ("1" = churned) as the SECOND level: glm models P(second level).
as_outcome <- function(y) factor(y, levels = c(0L, 1L))

fit_logistic <- function(x, y) {
  # TODO(M4) fit_logistic: unpenalised maximum-likelihood logistic regression (no regularisation: the contract
  # compares tracks to 1e-6, and every library's default penalty differs). Spec: contract/feature-spec.md §5;
  # tests: model.
  stop("TODO(M4) fit_logistic: see the comment above")
}

#' intercept + b1 * x1 + b2 * x2 + ..., added up in feature order, one element at a time. Not %*%: BLAS kernels may
#' add up rows in different orders (blocks, FMA), so two identical rows could score a last bit apart and break a tie.
linear_predictor <- function(fit, x) {
  # TODO(M4) linear_predictor: intercept + b1 * x1 + b2 * x2 + ... added feature by feature, NOT a matrix
  # product: BLAS kernels add rows in different orders, so two identical customers could score an ulp apart and
  # break a tie. Spec: contract/feature-spec.md §5; tests: model.
  stop("TODO(M4) linear_predictor: see the comment above")
}

predict_logistic <- function(fit, x) {
  # TODO(M4) predict_logistic: the logistic of the linear predictor. Spec: contract/feature-spec.md §5; tests:
  # model.
  stop("TODO(M4) predict_logistic: see the comment above")
}

#' B1: one point per risk flag of the contract's rule_baseline.
rule_score <- function(x, rules) {
  # TODO(M4) rule_score: B1: one point per risk flag of the contract's rule_baseline. Spec:
  # contract/feature-spec.md §5; tests: model.
  stop("TODO(M4) rule_score: see the comment above")
}

#' The churn rate of the training rows for each flag count (a lookup table), the overall rate for unseen counts.
fit_rule <- function(x, y, rules) {
  # TODO(M4) fit_rule: the training churn rate for each flag count; the overall rate for a count never seen in
  # training. Spec: contract/feature-spec.md §5; tests: model.
  stop("TODO(M4) fit_rule: see the comment above")
}

predict_rule <- function(fit, x, rules) {
  # TODO(M4) predict_rule: look up the rate of each row's flag count. Spec: contract/feature-spec.md §5; tests:
  # model.
  stop("TODO(M4) predict_rule: see the comment above")
}

fit_prior <- function(y) {
  # TODO(M4) fit_prior: B0: the training churn rate. Spec: contract/feature-spec.md §5; tests: model.
  stop("TODO(M4) fit_prior: see the comment above")
}

predict_prior <- function(fit, x) {
  # TODO(M4) predict_prior: everyone gets the training churn rate (AUC exactly 0.5). Spec:
  # contract/feature-spec.md §5; tests: model.
  stop("TODO(M4) predict_prior: see the comment above")
}

#' The contract's grouped folds (customer number mod 5) as an rsample rset: a customer never sits in two folds.
contract_folds <- function(train, folds) {
  # TODO(M4) contract_folds: an rsample manual_rset from the contract's folds (never vfold_cv: it would split
  # customers). Spec: contract/feature-spec.md §5; tests: model.
  stop("TODO(M4) contract_folds: see the comment above")
}
