-- M7 · Monitoring and retraining (contract/feature-spec.md §9). The runner has filled `post_scored`
-- (model, customer_id, snapshot, split, y, p) with:
--   champion:   the deployed model's score on the training rows and every post-deployment row (or, on an export
--               without labelled post-deployment months, this run's champion on its training rows);
--   challenger: the refitted, recalibrated model on its refit rows, the recent month and the holdout month.
-- Variables: psi_bins, psi_floor, psi_watch, psi_drift, alert_*, rt_*, top_percent, fairness_*, missing_label.

-- PSI reference edges: the decile edges (type-7 quantiles, = quantile_cont) of each variable, duplicates dropped.
-- t has the columns (var, value).
CREATE OR REPLACE MACRO psi_edges_of(t) AS TABLE  -- noqa: CP05
WITH q AS (
    SELECT
        var,
        quantile_cont(value, [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]) AS qs
    FROM query_table(t)
    GROUP BY var
)

SELECT DISTINCT
    var,
    unnest(qs) AS edge
FROM q;

-- the share of rows in each bin; bin of a value = the number of edges strictly below it, so a value equal to an edge
-- goes in the lower bin. t has the columns (grp, var, value), e the columns (var, edge). Empty bins are kept (share 0).
CREATE OR REPLACE MACRO bin_shares_of(t, e) AS TABLE  -- noqa: CP05
WITH v AS (
    SELECT
        grp,
        var,
        value,
        row_number() OVER () AS rid
    FROM query_table(t)
),

binned AS (
    SELECT
        v.rid,
        any_value(v.grp) AS grp,
        any_value(v.var) AS var,
        count(x.edge) AS bin
    FROM v
    LEFT JOIN query_table(e) AS x ON v.var = x.var AND x.edge < v.value
    GROUP BY v.rid
),

totals AS (
    SELECT
        grp,
        var,
        count(*) AS n
    FROM binned
    GROUP BY grp, var
),

grid AS (
    SELECT
        t.grp,
        t.var,
        t.n,
        CAST(k.k AS INTEGER) AS bin
    FROM totals AS t
    INNER JOIN (SELECT var, count(*) AS n_edges FROM query_table(e) GROUP BY var) AS ne ON t.var = ne.var
    CROSS JOIN LATERAL range(ne.n_edges + 1) AS k (k)
)

SELECT
    g.grp,
    g.var,
    g.bin,
    count(b.rid) / any_value(g.n) AS share
FROM grid AS g
LEFT JOIN binned AS b ON g.grp = b.grp AND g.var = b.var AND g.bin = b.bin
GROUP BY g.grp, g.var, g.bin;

-- the deployed (champion) model's features and score, per row ----------------------------------------------------
CREATE OR REPLACE TABLE monitor_values AS
SELECT
    CASE WHEN s.split = 'train' THEN 'reference' ELSE s.snapshot END AS grp,
    l.feature AS var,
    l.value
FROM post_scored AS s
INNER JOIN feature_long AS l ON s.customer_id = l.customer_id AND s.snapshot = l.snapshot
INNER JOIN cfg_model_features AS m ON l.feature = m.name AND m.model = 'champion'
WHERE s.model = 'champion'
UNION ALL
SELECT
    CASE WHEN split = 'train' THEN 'reference' ELSE snapshot END AS grp,
    '__score__' AS var,
    p AS value
FROM post_scored
WHERE model = 'champion';

CREATE OR REPLACE VIEW monitor_reference AS
SELECT
    var,
    value
FROM monitor_values
WHERE grp = 'reference';

CREATE OR REPLACE TABLE monitor_edges AS
SELECT * FROM psi_edges_of(monitor_reference);

CREATE OR REPLACE TABLE monitor_shares AS
SELECT * FROM bin_shares_of(monitor_values, monitor_edges);

-- PSI = sum over bins of (a - e) * ln(a / e), empty bins counted at psi_floor
CREATE OR REPLACE TABLE drift AS
SELECT
    a.grp AS snapshot,
    a.var,
    sum(
        (greatest(a.share, getvariable('psi_floor')) - greatest(e.share, getvariable('psi_floor')))
        * ln(greatest(a.share, getvariable('psi_floor')) / greatest(e.share, getvariable('psi_floor')))
    ) AS psi
FROM monitor_shares AS a
INNER JOIN monitor_shares AS e ON a.var = e.var AND a.bin = e.bin AND e.grp = 'reference'
WHERE a.grp <> 'reference'
GROUP BY a.grp, a.var;

CREATE OR REPLACE TABLE drift_status AS
SELECT
    snapshot,
    var,
    psi,
    CASE
        WHEN psi >= getvariable('psi_drift') THEN 'drift'
        WHEN psi >= getvariable('psi_watch') THEN 'watch'
        ELSE 'stable'
    END AS status
FROM drift;

-- realised performance of the deployed model on the labelled post-deployment months -------------------------------
CREATE OR REPLACE VIEW performance_groups AS
SELECT
    snapshot AS grp,
    y,
    p
FROM post_scored
WHERE model = 'champion' AND split IN ('recent', 'holdout');

CREATE OR REPLACE TABLE monitor_performance AS
SELECT
    s.grp AS snapshot,
    s.rows,
    a.auc,
    s.brier,
    s.ece,
    s.mean_pred,
    s.observed_rate,
    s.ece > getvariable('alert_max_ece') AS alert_ece,
    abs(s.mean_pred - s.observed_rate) > getvariable('alert_max_mean_gap') AS alert_mean_gap,
    a.auc < getvariable('alert_min_auc') AS alert_auc
FROM probability_scores_of(performance_groups) AS s
INNER JOIN auc_of(performance_groups) AS a ON s.grp = a.grp;

-- champion vs challenger on the holdout month ---------------------------------------------------------------------
CREATE OR REPLACE TABLE holdout_scored AS
SELECT
    s.model,
    s.customer_id,
    s.snapshot,
    s.y,
    s.p,
    f.price_inr,
    CASE getvariable('fairness_dimension')
        WHEN 'age_band' THEN f.age_band WHEN 'city_tier' THEN f.city_tier WHEN 'plan' THEN f.plan
        WHEN 'channel' THEN f.channel WHEN 'city' THEN f.city
    END AS fairness_value,
    row_number() OVER (PARTITION BY s.model, s.snapshot ORDER BY s.p DESC, s.customer_id)
    <= top_k(count(*) OVER (PARTITION BY s.model, s.snapshot), getvariable('top_percent')) AS contacted
FROM post_scored AS s
INNER JOIN features AS f ON s.customer_id = f.customer_id AND s.snapshot = f.snapshot
WHERE s.split = 'holdout';

CREATE OR REPLACE VIEW holdout_groups AS
SELECT
    model AS grp,
    y,
    p
FROM holdout_scored;

CREATE OR REPLACE TABLE holdout_recall AS
SELECT
    model,
    max(recall) - min(recall) AS recall_gap
FROM (
    SELECT
        model,
        fairness_value,
        count(*) FILTER (WHERE contacted AND y = 1) / sum(y) AS recall
    FROM holdout_scored
    WHERE fairness_value <> getvariable('missing_label')
    GROUP BY model, fairness_value
    HAVING sum(y) >= getvariable('fairness_min_churners')
)
GROUP BY model;

CREATE OR REPLACE TABLE holdout_metrics AS
SELECT
    s.grp AS model,
    s.rows,
    a.auc,
    ap.average_precision,
    s.brier,
    s.log_loss,
    s.ece,
    count(*) FILTER (WHERE h.contacted) AS contacted,
    sum(h.y) FILTER (WHERE h.contacted) AS churners_reached,
    sum(h.y) FILTER (WHERE h.contacted) / count(*) FILTER (WHERE h.contacted) AS precision_at_top,
    sum(h.y) FILTER (WHERE h.contacted) / sum(h.y) AS recall_at_top,
    (sum(h.y) FILTER (WHERE h.contacted) / count(*) FILTER (WHERE h.contacted)) / avg(h.y) AS lift_at_top,
    (
        sum(h.y * h.price_inr) FILTER (WHERE h.contacted) * getvariable('save_rate') * getvariable('value_months')
        - getvariable('offer_cost_inr') * count(*) FILTER (WHERE h.contacted)
    ) / count(DISTINCT h.snapshot) AS net_value_inr_per_month,
    s.mean_pred,
    s.observed_rate,
    r.recall_gap
FROM probability_scores_of(holdout_groups) AS s
INNER JOIN auc_of(holdout_groups) AS a ON s.grp = a.grp
INNER JOIN ap_of(holdout_groups) AS ap ON s.grp = ap.grp
INNER JOIN holdout_scored AS h ON s.grp = h.model
INNER JOIN holdout_recall AS r ON s.grp = r.model
GROUP BY ALL;

CREATE OR REPLACE TABLE retraining_gate AS
WITH ch AS (SELECT * FROM holdout_metrics WHERE model = 'champion'),

cc AS (SELECT * FROM holdout_metrics WHERE model = 'challenger')

SELECT
    1 AS pos,
    'auc_not_worse' AS id,
    cc.auc AS value,
    ch.auc - getvariable('rt_max_auc_drop') AS threshold,
    cc.auc >= ch.auc - getvariable('rt_max_auc_drop') AS passed
FROM ch, cc
UNION ALL
SELECT
    2 AS pos,
    'brier_improves' AS id,
    cc.brier AS value,
    ch.brier AS threshold,
    cc.brier < ch.brier AS passed
FROM ch, cc
UNION ALL
SELECT
    3 AS pos,
    'ece' AS id,
    cc.ece AS value,
    getvariable('rt_max_ece') AS threshold,
    cc.ece <= getvariable('rt_max_ece') AS passed
FROM cc
UNION ALL
SELECT
    4 AS pos,
    'recall_gap' AS id,
    cc.recall_gap AS value,
    getvariable('rt_max_recall_gap') AS threshold,
    cc.recall_gap <= getvariable('rt_max_recall_gap') AS passed
FROM cc;

-- the profile stored in the new artefact: the model it describes on the rows it was fitted on ----------------------
CREATE OR REPLACE TABLE profile_values AS
WITH artefact_model AS (
    SELECT CASE WHEN count(*) > 0 THEN 'challenger' ELSE 'champion' END AS model
    FROM post_scored
    WHERE model = 'challenger'
),

rows AS (
    SELECT s.*
    FROM post_scored AS s
    INNER JOIN artefact_model AS a ON s.model = a.model
    WHERE s.split IN (SELECT split FROM cfg_profile_splits)
)

SELECT
    'profile' AS grp,
    l.feature AS var,
    l.value
FROM rows AS s
INNER JOIN feature_long AS l ON s.customer_id = l.customer_id AND s.snapshot = l.snapshot
INNER JOIN cfg_model_features AS m ON l.feature = m.name AND m.model = 'artefact'
UNION ALL
SELECT
    'profile' AS grp,
    '__score__' AS var,
    p AS value
FROM rows;

CREATE OR REPLACE TABLE profile_edges AS
SELECT * FROM psi_edges_of(profile_values);

CREATE OR REPLACE TABLE profile_shares AS
SELECT * FROM bin_shares_of(profile_values, profile_edges);
