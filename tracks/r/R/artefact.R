# M5 · The model artefact (out/model.json): language-neutral, so the API can serve a model trained by any track.
# Schema: contract/model.schema.json. Explanations are exact for a linear model: the contribution of feature j is
# beta_j * (x_j - mean_j) on the log-odds scale (the training mean is the baseline).

SCHEMA_VERSION <- "1.0"

build_artefact <- function(fit, experiment, features, means, threshold, base_rate, training, test_metrics,
                           version, track) {
  list(
    schema_version = SCHEMA_VERSION,
    name = "churncast",
    model_version = version,
    kind = "logistic_regression",
    target = "churned_next_month",
    experiment = experiment,
    features = as.list(features),
    intercept = fit$intercept,
    coefficients = fit$coefficients[features],
    feature_means = means[features],
    high_risk_threshold = threshold,
    base_rate = base_rate,
    training = training,
    test_metrics = test_metrics,
    generator = list(track = track, version = version)
  )
}

score <- function(artefact, row) {
  eta <- artefact$intercept + sum(vapply(names(artefact$coefficients), function(f) {
    artefact$coefficients[[f]] * as.numeric(row[[f]])
  }, numeric(1)))
  1 / (1 + exp(-eta))
}

#' Per-feature log-odds contributions, largest absolute first (ties: contract order).
contributions <- function(artefact, row) {
  out <- lapply(names(artefact$coefficients), function(f) {
    value <- as.numeric(row[[f]])
    list(feature = f, value = value, contribution = artefact$coefficients[[f]] * (value - artefact$feature_means[[f]]))
  })
  size <- vapply(out, function(r) abs(r$contribution), numeric(1))
  out[order(-size, seq_along(out))]
}
