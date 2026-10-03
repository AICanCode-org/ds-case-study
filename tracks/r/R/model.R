# M4 · Baselines and the logistic regression (contract/feature-spec.md §5), with tidymodels.
#
# The model is parsnip's logistic_reg() on the "glm" engine inside a workflow: unpenalised maximum likelihood, the
# same estimate scikit-learn's Newton-Cholesky solver finds in the Python track. glm's convergence tolerance is
# tightened (epsilon 1e-12) so the coefficients agree to far better than the parity tolerance.

logistic_spec <- function() {
  parsnip::logistic_reg() |>
    parsnip::set_engine("glm", control = stats::glm.control(epsilon = 1e-12, maxit = 100))
}

#' The outcome as a factor with the event ("1" = churned) as the SECOND level: glm models P(second level).
as_outcome <- function(y) factor(y, levels = c(0L, 1L))

fit_logistic <- function(x, y) {
  data <- x
  data$churned <- as_outcome(y)
  wf <- workflows::workflow() |>
    workflows::add_formula(churned ~ .) |>
    workflows::add_model(logistic_spec())
  fitted <- parsnip::fit(wf, data = data)
  engine <- workflows::extract_fit_engine(fitted)
  if (!engine$converged) stop("glm did not converge")
  beta <- stats::coef(engine)
  list(intercept = unname(beta[["(Intercept)"]]),
       coefficients = as.list(beta[names(x)]),
       workflow = fitted)
}

#' intercept + b1 * x1 + b2 * x2 + ..., added up in feature order, one element at a time. Not %*%: BLAS kernels may
#' add up rows in different orders (blocks, FMA), so two identical rows could score a last bit apart and break a tie.
linear_predictor <- function(fit, x) {
  eta <- rep(fit$intercept, nrow(x))
  for (f in names(fit$coefficients)) eta <- eta + fit$coefficients[[f]] * as.numeric(x[[f]])
  eta
}

predict_logistic <- function(fit, x) 1 / (1 + exp(-linear_predictor(fit, x)))

#' B1: one point per risk flag of the contract's rule_baseline.
rule_score <- function(x, rules) {
  score <- integer(nrow(x))
  for (r in rules) {
    v <- as.numeric(x[[r$feature]])
    score <- score + as.integer(if (r$op == ">=") v >= r$value else v <= r$value)
  }
  score
}

#' The churn rate of the training rows for each flag count (a lookup table), the overall rate for unseen counts.
fit_rule <- function(x, y, rules) {
  score <- rule_score(x, rules)
  rates <- tapply(as.numeric(y), score, mean)
  list(rates = stats::setNames(as.numeric(rates), names(rates)), default = mean(as.numeric(y)))
}

predict_rule <- function(fit, x, rules) {
  key <- as.character(rule_score(x, rules))
  p <- unname(fit$rates[key])
  ifelse(is.na(p), fit$default, p)
}

fit_prior <- function(y) list(rate = mean(as.numeric(y)))

predict_prior <- function(fit, x) rep(fit$rate, nrow(x))

#' The contract's grouped folds (customer number mod 5) as an rsample rset: a customer never sits in two folds.
contract_folds <- function(train, folds) {
  splits <- lapply(seq_len(folds) - 1L, function(k) {
    rsample::make_splits(list(analysis = which(train$fold != k), assessment = which(train$fold == k)), data = train)
  })
  rsample::manual_rset(splits, ids = paste0("Fold", seq_len(folds) - 1L))
}
