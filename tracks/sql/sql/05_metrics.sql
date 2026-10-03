-- M4 · The metrics, written once as table macros over any table or view with the columns (grp, y, p): one result
-- row per group. Every number of the evaluation goes through these, and tests/unit/test_metrics.py checks them
-- against contract/fixtures/metric-cases.json. Variables: calibration_bins, eps.

-- AUC = P(score of a churner > score of a stayer); ties count 1/2 (average ranks). NULL with one class only.
-- TODO(M4) auc_of: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: tests/unit/test_metrics.py
CREATE OR REPLACE MACRO auc_of(t) AS TABLE  -- noqa: CP05
SELECT NULL AS todo;

-- average precision: sum over distinct scores, high to low, of (recall_k - recall_k-1) * precision_k
-- TODO(M4) ap_of: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: tests/unit/test_metrics.py
CREATE OR REPLACE MACRO ap_of(t) AS TABLE  -- noqa: CP05
SELECT NULL AS todo;

-- calibration: equal-width bins of the predicted probability (bin k = [k/B, (k+1)/B), p = 1 goes in the last one)
-- TODO(M4) calibration_of: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: tests/unit/test_metrics.py
CREATE OR REPLACE MACRO calibration_of(t) AS TABLE  -- noqa: CP05
SELECT NULL AS todo;

-- Brier score, log loss (p clipped to [eps, 1 - eps]), mean prediction, observed rate and the expected calibration
-- error (ECE = sum over bins of n_b / n * |mean predicted - observed|)
-- TODO(M4) probability_scores_of: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: tests/unit/test_metrics.py
CREATE OR REPLACE MACRO probability_scores_of(t) AS TABLE  -- noqa: CP05
SELECT NULL AS todo;

-- how many customers the team can call: ceil(n * percent / 100) in integers (no floating-point surprise)
-- TODO(M4) top_k: contract/feature-spec.md §6 (+ contract/fixtures/metric-cases.json); tests: tests/unit/test_metrics.py
CREATE OR REPLACE MACRO top_k(n, pct) AS NULL;  -- noqa: CP05
