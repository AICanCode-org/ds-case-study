-- M4-M5 · Evaluation (contract/feature-spec.md §6) of every fit in `scored`: the metrics of 05_metrics.sql per
-- experiment and stage, the cross-validation summary, the retention-capacity view (top 10 % of each month), slices,
-- fairness, the leakage scan, the champion choice and the gate. Variables: top_percent, offer_cost_inr, save_rate,
-- value_months, min_slice_rows, min_slice_churners, fairness_*, leakage_limit, min_gain, gate_*.

-- TODO(M5) scored_groups: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE VIEW scored_groups AS
SELECT NULL AS todo;

-- TODO(M5) fit_metrics: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE TABLE fit_metrics AS
SELECT NULL AS todo;

-- TODO(M5) calibration_bins: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE TABLE calibration_bins AS
SELECT NULL AS todo;

-- cross-validation summary: mean and sample SD over the folds ------------------------------------------------
-- TODO(M5) cv_summary: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE TABLE cv_summary AS
SELECT NULL AS todo;

-- the test predictions with the slice columns, and who is contacted (top k of each month; ties: lower id first)
-- TODO(M5) test_scored: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE TABLE test_scored AS
SELECT NULL AS todo;

-- TODO(M5) capacity: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE TABLE capacity AS
SELECT NULL AS todo;

-- slices and fairness ------------------------------------------------------------------------------------------
-- TODO(M5) slice_input: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE TABLE slice_input AS
SELECT NULL AS todo;

-- TODO(M5) slice_groups: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE VIEW slice_groups AS
SELECT NULL AS todo;

-- TODO(M5) slices: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE TABLE slices AS
SELECT NULL AS todo;

-- TODO(M5) fairness: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE TABLE fairness AS
SELECT NULL AS todo;

-- leakage scan: the AUC of every single feature on the training rows (folded to >= 0.5), and of the leaky probe ----
-- TODO(M5) leakage_groups: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE VIEW leakage_groups AS
SELECT NULL AS todo;

-- TODO(M5) leakage: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE TABLE leakage AS
SELECT NULL AS todo;

-- the champion: the bigger logistic experiment only if it beats the simpler one by the contract's margin ----------
-- TODO(M5) champion: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE TABLE champion AS
SELECT NULL AS todo;

-- the evaluation gate: every check must pass before the model can ship -----------------------------------------
-- TODO(M5) gate: contract/feature-spec.md §5-§6; tests: tests/unit/test_evaluate.py
CREATE OR REPLACE TABLE gate AS
SELECT NULL AS todo;
