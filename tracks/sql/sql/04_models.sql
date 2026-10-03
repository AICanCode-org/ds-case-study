-- M4 · Baselines and the cross-validation layout (contract/feature-spec.md §5).
-- cfg_stages lists every fit: cv0..cv4 fit on the other training folds and score fold k; 'test' and 'train' fit on
-- all training rows and score the test snapshots or the training rows. B0 and B1 are fitted right here in SQL;
-- the logistic regressions are fitted by the runner (the one step SQL cannot do) and scored back into `scored`.

CREATE OR REPLACE VIEW stage_rows AS
SELECT
    s.stage,
    'fit' AS role,
    f.customer_id,
    f.snapshot
FROM cfg_stages AS s
INNER JOIN features AS f ON f.split = 'train' AND (s.fold IS NULL OR f.fold <> s.fold)
UNION ALL
SELECT
    s.stage,
    'eval' AS role,
    f.customer_id,
    f.snapshot
FROM cfg_stages AS s
INNER JOIN features AS f ON f.split = s.eval_split AND (s.fold IS NULL OR f.fold = s.fold);

CREATE OR REPLACE TABLE scored (
    exp_id VARCHAR, stage VARCHAR, customer_id VARCHAR, snapshot VARCHAR, y INTEGER, p DOUBLE
);

-- B0 · prior: everyone gets the churn rate of the fit rows
CREATE OR REPLACE VIEW stage_prior AS
SELECT
    r.stage,
    avg(f.churned) AS rate
FROM stage_rows AS r
INNER JOIN features AS f ON r.customer_id = f.customer_id AND r.snapshot = f.snapshot
WHERE r.role = 'fit'
GROUP BY r.stage;

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
CREATE OR REPLACE TABLE rule_points AS
SELECT
    f.customer_id,
    f.snapshot,
    coalesce(sum(
        CASE
            WHEN ru.op = '>=' THEN CAST(l.value >= ru.value AS INTEGER)
            WHEN ru.op = '<=' THEN CAST(l.value <= ru.value AS INTEGER)
        END
    ), 0) AS points
FROM features AS f
LEFT JOIN feature_long AS l ON f.customer_id = l.customer_id AND f.snapshot = l.snapshot
LEFT JOIN cfg_rules AS ru ON l.feature = ru.feature
GROUP BY f.customer_id, f.snapshot;

CREATE OR REPLACE VIEW stage_rule_rates AS
SELECT
    r.stage,
    rp.points,
    avg(f.churned) AS rate
FROM stage_rows AS r
INNER JOIN features AS f ON r.customer_id = f.customer_id AND r.snapshot = f.snapshot
INNER JOIN rule_points AS rp ON r.customer_id = rp.customer_id AND r.snapshot = rp.snapshot
WHERE r.role = 'fit'
GROUP BY r.stage, rp.points;

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
