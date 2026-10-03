-- M4 · Baselines and the cross-validation layout (contract/feature-spec.md §5).
-- cfg_stages lists every fit: cv0..cv4 fit on the other training folds and score fold k; 'test' and 'train' fit on
-- all training rows and score the test snapshots or the training rows. B0 and B1 are fitted right here in SQL;
-- the logistic regressions are fitted by the runner (the one step SQL cannot do) and scored back into `scored`.

-- TODO(M4) stage_rows: contract/feature-spec.md §5; tests: tests/unit/test_model.py
CREATE OR REPLACE VIEW stage_rows AS
SELECT NULL AS todo;

CREATE OR REPLACE TABLE scored (
    exp_id VARCHAR, stage VARCHAR, customer_id VARCHAR, snapshot VARCHAR, y INTEGER, p DOUBLE
);

-- B0 · prior: everyone gets the churn rate of the fit rows
-- TODO(M4) stage_prior: contract/feature-spec.md §5; tests: tests/unit/test_model.py
CREATE OR REPLACE VIEW stage_prior AS
SELECT NULL AS todo;

INSERT INTO scored
SELECT
    getvariable('prior_id'),
    r.stage,
    r.customer_id,
    r.snapshot,
    f.churned,
    pr.rate
FROM stage_rows AS r
INNER JOIN features AS f ON r.customer_id = f.customer_id AND r.snapshot = f.snapshot
INNER JOIN stage_prior AS pr ON r.stage = pr.stage
WHERE r.role = 'eval';

-- B1 · rule of thumb: one point per flag of cfg_rules, then the churn rate of the fit rows per point count
-- TODO(M4) rule_points: contract/feature-spec.md §5; tests: tests/unit/test_model.py
CREATE OR REPLACE TABLE rule_points AS
SELECT NULL AS todo;

-- TODO(M4) stage_rule_rates: contract/feature-spec.md §5; tests: tests/unit/test_model.py
CREATE OR REPLACE VIEW stage_rule_rates AS
SELECT NULL AS todo;

INSERT INTO scored
SELECT
    getvariable('rule_id'),
    r.stage,
    r.customer_id,
    r.snapshot,
    f.churned,
    coalesce(rr.rate, pr.rate)
FROM stage_rows AS r
INNER JOIN features AS f ON r.customer_id = f.customer_id AND r.snapshot = f.snapshot
INNER JOIN rule_points AS rp ON r.customer_id = rp.customer_id AND r.snapshot = rp.snapshot
INNER JOIN stage_prior AS pr ON r.stage = pr.stage
LEFT JOIN stage_rule_rates AS rr ON r.stage = rr.stage AND rp.points = rr.points
WHERE r.role = 'eval';
