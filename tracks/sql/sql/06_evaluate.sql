-- M4-M5 · Evaluation (contract/feature-spec.md §6) of every fit in `scored`: the metrics of 05_metrics.sql per
-- experiment and stage, the cross-validation summary, the retention-capacity view (top 10 % of each month), slices,
-- fairness, the leakage scan, the champion choice and the gate. Variables: top_percent, offer_cost_inr, save_rate,
-- value_months, min_slice_rows, min_slice_churners, fairness_*, leakage_limit, min_gain, gate_*.

CREATE OR REPLACE VIEW scored_groups AS
SELECT
    exp_id || '/' || stage AS grp,
    y,
    p
FROM scored;

CREATE OR REPLACE TABLE fit_metrics AS
SELECT
    split_part(s.grp, '/', 1) AS exp_id,
    split_part(s.grp, '/', 2) AS stage,
    s.rows,
    s.brier,
    s.log_loss,
    s.mean_pred,
    s.observed_rate,
    s.ece,
    a.auc,
    ap.average_precision
FROM probability_scores_of(scored_groups) AS s
INNER JOIN auc_of(scored_groups) AS a ON s.grp = a.grp
INNER JOIN ap_of(scored_groups) AS ap ON s.grp = ap.grp;

CREATE OR REPLACE TABLE calibration_bins AS
SELECT
    split_part(grp, '/', 1) AS exp_id,
    split_part(grp, '/', 2) AS stage,
    bin,
    lower,
    upper,
    n,
    mean_pred,
    observed
FROM calibration_of(scored_groups);

-- cross-validation summary: mean and sample SD over the folds ------------------------------------------------
CREATE OR REPLACE TABLE cv_summary AS
SELECT
    exp_id,
    avg(auc) AS auc_mean,
    stddev_samp(auc) AS auc_sd,
    avg(brier) AS brier_mean,
    avg(log_loss) AS log_loss_mean
FROM fit_metrics
WHERE stage LIKE 'cv%'
GROUP BY exp_id;

-- the test predictions with the slice columns, and who is contacted (top k of each month; ties: lower id first)
CREATE OR REPLACE TABLE test_scored AS
SELECT
    sc.exp_id,
    sc.customer_id,
    sc.snapshot,
    sc.y,
    sc.p,
    f.price_inr,
    f.age_band,
    f.city_tier,
    f.plan,
    f.channel,
    f.city,
    row_number() OVER (PARTITION BY sc.exp_id, sc.snapshot ORDER BY sc.p DESC, sc.customer_id)
    <= top_k(count(*) OVER (PARTITION BY sc.exp_id, sc.snapshot), getvariable('top_percent')) AS contacted
FROM scored AS sc
INNER JOIN features AS f ON sc.customer_id = f.customer_id AND sc.snapshot = f.snapshot
WHERE sc.stage = 'test';

CREATE OR REPLACE TABLE capacity AS
SELECT
    exp_id,
    count(*) FILTER (WHERE contacted) AS contacted,
    sum(y) FILTER (WHERE contacted) AS churners_reached,
    sum(y) FILTER (WHERE contacted) / count(*) FILTER (WHERE contacted) AS precision_at_top,
    sum(y) FILTER (WHERE contacted) / sum(y) AS recall_at_top,
    (sum(y) FILTER (WHERE contacted) / count(*) FILTER (WHERE contacted)) / avg(y) AS lift_at_top,
    (
        sum(y * price_inr) FILTER (WHERE contacted) * getvariable('save_rate') * getvariable('value_months')
        - getvariable('offer_cost_inr') * count(*) FILTER (WHERE contacted)
    ) / count(DISTINCT snapshot) AS net_value_inr_per_month
FROM test_scored
GROUP BY exp_id;

-- slices and fairness ------------------------------------------------------------------------------------------
CREATE OR REPLACE TABLE slice_input AS
SELECT
    t.exp_id,
    d.pos AS dim_pos,
    d.dim,
    CASE d.dim
        WHEN 'age_band' THEN t.age_band WHEN 'city_tier' THEN t.city_tier WHEN 'plan' THEN t.plan
        WHEN 'channel' THEN t.channel WHEN 'city' THEN t.city
    END AS value,
    t.y,
    t.p,
    t.contacted
FROM test_scored AS t
CROSS JOIN cfg_slices AS d;

CREATE OR REPLACE VIEW slice_groups AS
SELECT
    exp_id || '/' || dim || '/' || value AS grp,
    y,
    p
FROM slice_input;

CREATE OR REPLACE TABLE slices AS
SELECT
    s.exp_id,
    s.dim_pos,
    s.dim,
    s.value,
    count(*) AS n,
    sum(s.y) AS churners,
    sum(s.y) / count(*) AS churn_rate,
    avg(s.p) AS mean_pred,
    CASE
        WHEN
            count(*) >= getvariable('min_slice_rows')
            AND least(sum(s.y), count(*) - sum(s.y)) >= getvariable('min_slice_churners')
            THEN any_value(a.auc)
    END AS auc,
    count(*) FILTER (WHERE s.contacted) AS contacted,
    count(*) FILTER (WHERE s.contacted) / count(*) AS flagged_rate,
    CASE WHEN sum(s.y) > 0 THEN count(*) FILTER (WHERE s.contacted AND s.y = 1) / sum(s.y) END AS recall_at_top
FROM slice_input AS s
LEFT JOIN auc_of(slice_groups) AS a ON a.grp = s.exp_id || '/' || s.dim || '/' || s.value
GROUP BY s.exp_id, s.dim_pos, s.dim, s.value;

CREATE OR REPLACE TABLE fairness AS
SELECT
    exp_id,
    list(value ORDER BY value) AS groups,
    max(recall_at_top) - min(recall_at_top) AS recall_gap,
    CASE WHEN max(flagged_rate) > 0 THEN min(flagged_rate) / max(flagged_rate) END AS flagged_rate_ratio
FROM slices
WHERE
    dim = getvariable('fairness_dimension')
    AND value <> getvariable('missing_label')
    AND churners >= getvariable('fairness_min_churners')
GROUP BY exp_id;

-- leakage scan: the AUC of every single feature on the training rows (folded to >= 0.5), and of the leaky probe ----
CREATE OR REPLACE VIEW leakage_groups AS
SELECT
    'feature/' || l.feature AS grp,
    f.churned AS y,
    l.value AS p
FROM feature_long AS l
INNER JOIN features AS f ON l.customer_id = f.customer_id AND l.snapshot = f.snapshot
WHERE f.split = 'train'
UNION ALL
SELECT
    'probe/cancellation_reason' AS grp,
    f.churned AS y,
    CAST(trim(c.cancellation_reason) <> '' AS DOUBLE) AS p
FROM features AS f
INNER JOIN customers AS c ON f.customer_id = c.customer_id
WHERE f.split = 'train';

CREATE OR REPLACE TABLE leakage AS
SELECT
    split_part(a.grp, '/', 1) AS kind,
    split_part(a.grp, '/', 2) AS name,
    greatest(a.auc, 1 - a.auc) AS auc,
    coalesce(f.pos, 0) AS pos
FROM auc_of(leakage_groups) AS a
LEFT JOIN cfg_features AS f ON split_part(a.grp, '/', 2) = f.name;

-- the champion: the bigger logistic experiment only if it beats the simpler one by the contract's margin ----------
CREATE OR REPLACE TABLE champion AS
WITH logistic AS (
    SELECT
        e.id,
        e.pos,
        cv.auc_mean
    FROM cfg_experiments AS e
    INNER JOIN cv_summary AS cv ON e.id = cv.exp_id
    WHERE e.kind = 'logistic'
),

pair AS (
    SELECT
        (SELECT l.id FROM logistic AS l ORDER BY l.pos LIMIT 1) AS simple_id,
        (SELECT l.id FROM logistic AS l ORDER BY l.pos DESC LIMIT 1) AS bigger_id,
        (SELECT l.auc_mean FROM logistic AS l ORDER BY l.pos DESC LIMIT 1)
        - (SELECT l.auc_mean FROM logistic AS l ORDER BY l.pos LIMIT 1) AS gain
)

SELECT
    simple_id,
    bigger_id,
    gain,
    CASE WHEN gain >= getvariable('min_gain') THEN bigger_id ELSE simple_id END AS champion_id
FROM pair;

-- the evaluation gate: every check must pass before the model can ship -----------------------------------------
CREATE OR REPLACE TABLE gate AS
WITH test AS (
    SELECT * FROM fit_metrics WHERE stage = 'test'
),

champ AS (
    SELECT t.* FROM test AS t INNER JOIN champion AS c ON t.exp_id = c.champion_id
),

worst AS (
    SELECT l.auc FROM leakage AS l WHERE l.kind = 'feature' ORDER BY l.auc DESC, l.pos LIMIT 1
)

SELECT
    1 AS pos,
    'test_auc' AS id,
    champ.auc AS value,
    getvariable('gate_min_test_auc') AS threshold,
    champ.auc >= getvariable('gate_min_test_auc') AS passed
FROM champ
UNION ALL
SELECT
    2 AS pos,
    'auc_uplift_over_rule' AS id,
    champ.auc - r.auc AS value,
    getvariable('gate_min_auc_uplift') AS threshold,
    champ.auc - r.auc >= getvariable('gate_min_auc_uplift') AS passed
FROM champ, test AS r
WHERE r.exp_id = getvariable('rule_id')
UNION ALL
SELECT
    3 AS pos,
    'ece' AS id,
    champ.ece AS value,
    getvariable('gate_max_ece') AS threshold,
    champ.ece <= getvariable('gate_max_ece') AS passed
FROM champ
UNION ALL
SELECT
    4 AS pos,
    'brier_below_prior' AS id,
    champ.brier AS value,
    b.brier AS threshold,
    champ.brier < b.brier AS passed
FROM champ, test AS b
WHERE b.exp_id = getvariable('prior_id')
UNION ALL
SELECT
    5 AS pos,
    'recall_gap' AS id,
    f.recall_gap AS value,
    getvariable('gate_max_recall_gap') AS threshold,
    f.recall_gap <= getvariable('gate_max_recall_gap') AS passed
FROM fairness AS f INNER JOIN champion AS c ON f.exp_id = c.champion_id
UNION ALL
SELECT
    6 AS pos,
    'leakage_scan' AS id,
    worst.auc AS value,
    getvariable('leakage_limit') AS threshold,
    worst.auc < getvariable('leakage_limit') AS passed
FROM worst;
