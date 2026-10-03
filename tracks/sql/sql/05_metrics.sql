-- M4 · The metrics, written once as table macros over any table or view with the columns (grp, y, p): one result
-- row per group. Every number of the evaluation goes through these, and tests/unit/test_metrics.py checks them
-- against contract/fixtures/metric-cases.json. Variables: calibration_bins, eps.

-- AUC = P(score of a churner > score of a stayer); ties count 1/2 (average ranks). NULL with one class only.
CREATE OR REPLACE MACRO auc_of(t) AS TABLE  -- noqa: CP05
WITH ranked AS (
    SELECT
        grp,
        y,
        rank() OVER (PARTITION BY grp ORDER BY p) + (count(*) OVER (PARTITION BY grp, p) - 1) / 2 AS r
    FROM query_table(t)
)

SELECT
    grp,
    sum(y) AS n_pos,
    count(*) - sum(y) AS n_neg,
    CASE
        WHEN sum(y) > 0 AND count(*) > sum(y)
            THEN (sum(r) FILTER (WHERE y = 1) - sum(y) * (sum(y) + 1) / 2) / (sum(y) * (count(*) - sum(y)))
    END AS auc
FROM ranked
GROUP BY grp;

-- average precision: sum over distinct scores, high to low, of (recall_k - recall_k-1) * precision_k
CREATE OR REPLACE MACRO ap_of(t) AS TABLE  -- noqa: CP05
WITH by_score AS (
    SELECT
        grp,
        p,
        sum(y) AS tp,
        count(*) AS n
    FROM query_table(t)
    GROUP BY grp, p
),

cumulative AS (
    SELECT
        grp,
        sum(tp) OVER (PARTITION BY grp ORDER BY p DESC ROWS UNBOUNDED PRECEDING) AS tp,
        sum(n) OVER (PARTITION BY grp ORDER BY p DESC ROWS UNBOUNDED PRECEDING) AS n,
        sum(tp) OVER (PARTITION BY grp) AS pos
    FROM by_score
),

steps AS (
    SELECT
        grp,
        pos,
        tp / n AS step_precision,
        tp / pos - coalesce(lag(tp) OVER (PARTITION BY grp ORDER BY n), 0) / pos AS d_recall
    FROM cumulative
)

SELECT
    grp,
    CASE WHEN max(pos) > 0 THEN sum(d_recall * step_precision) END AS average_precision
FROM steps
GROUP BY grp;

-- calibration: equal-width bins of the predicted probability (bin k = [k/B, (k+1)/B), p = 1 goes in the last one)
CREATE OR REPLACE MACRO calibration_of(t) AS TABLE  -- noqa: CP05
WITH binned AS (
    SELECT
        grp,
        y,
        p,
        least(CAST(floor(p * getvariable('calibration_bins')) AS INTEGER), getvariable('calibration_bins') - 1) AS bin
    FROM query_table(t)
),

grid AS (
    SELECT
        g.grp,
        CAST(k.k AS INTEGER) AS bin
    FROM (SELECT DISTINCT grp FROM binned) AS g
    CROSS JOIN range(getvariable('calibration_bins')) AS k (k)
)

SELECT
    g.grp,
    g.bin,
    g.bin / getvariable('calibration_bins') AS lower,
    (g.bin + 1) / getvariable('calibration_bins') AS upper,
    count(b.p) AS n,
    avg(b.p) AS mean_pred,
    avg(b.y) AS observed
FROM grid AS g
LEFT JOIN binned AS b ON g.grp = b.grp AND g.bin = b.bin
GROUP BY g.grp, g.bin;

-- Brier score, log loss (p clipped to [eps, 1 - eps]), mean prediction, observed rate and the expected calibration
-- error (ECE = sum over bins of n_b / n * |mean predicted - observed|)
CREATE OR REPLACE MACRO probability_scores_of(t) AS TABLE  -- noqa: CP05
WITH clipped AS (
    SELECT
        grp,
        y,
        p,
        greatest(least(p, 1 - getvariable('eps')), getvariable('eps')) AS pc
    FROM query_table(t)
),

base AS (
    SELECT
        grp,
        count(*) AS rows,
        avg((p - y) ^ 2) AS brier,
        -avg(y * ln(pc) + (1 - y) * ln(1 - pc)) AS log_loss,
        avg(p) AS mean_pred,
        avg(y) AS observed_rate
    FROM clipped
    GROUP BY grp
),

ece AS (
    SELECT
        c.grp,
        sum(c.n / b.rows * abs(c.mean_pred - c.observed)) AS ece
    FROM calibration_of(t) AS c
    INNER JOIN base AS b ON c.grp = b.grp
    WHERE c.n > 0
    GROUP BY c.grp
)

SELECT
    b.*,
    e.ece
FROM base AS b
INNER JOIN ece AS e ON b.grp = e.grp;

-- how many customers the team can call: ceil(n * percent / 100) in integers (no floating-point surprise)
CREATE OR REPLACE MACRO top_k(n, pct) AS (n * pct + 99) // 100;  -- noqa: CP05
