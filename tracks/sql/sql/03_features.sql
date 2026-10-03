-- M3 · Snapshots, labels and point-in-time features (contract/feature-spec.md §3-§4).
-- A snapshot is the end of month M; the cut-off S is the first instant of month M+1. A feature may use invoices
-- and usage of months <= M, tickets created before S and resolutions before S. The label looks at M+1 only.
-- The runner fills cfg_snapshots (month index, label, split) with the contract snapshots the export covers and
-- sets the variables export_month, rating_default and folds.

CREATE OR REPLACE TABLE paid AS
SELECT
    customer_id,
    month,
    plan,
    list_price,
    discount
FROM (
    SELECT
        *,
        row_number() OVER (PARTITION BY customer_id, month ORDER BY invoice_id) AS rn
    FROM invoices
    WHERE kind = 'charge' AND status = 'paid'
)
WHERE rn = 1;

CREATE OR REPLACE VIEW snapshot_base AS
SELECT
    s.month AS snap_month,
    s.label AS snapshot,
    s.split,
    p.customer_id,
    p.plan,
    p.list_price,
    p.discount,
    c.signup_month,
    c.city,
    c.city_tier,
    c.acquisition_channel,
    c.age_band,
    CAST(make_date((s.month + 1) // 12, (s.month + 1) % 12 + 1, 1) AS TIMESTAMP) AS cut
FROM cfg_snapshots AS s
INNER JOIN paid AS p ON s.month = p.month
INNER JOIN customers AS c ON p.customer_id = c.customer_id;

CREATE OR REPLACE VIEW snapshot_inputs AS
SELECT
    b.*,
    b.snap_month - b.signup_month AS tenure,
    CASE
        WHEN b.snap_month + 1 <= getvariable('export_month') THEN CAST(nxt.customer_id IS NULL AS INTEGER)
    END AS churned,
    prv.list_price AS prev_price,
    coalesce(u0.meals_ordered, 0) AS meals0,
    coalesce(u1.meals_ordered, 0) AS meals1,
    coalesce(u2.meals_ordered, 0) AS meals2,
    coalesce(u0.meals_skipped, 0) AS skipped0,
    coalesce(u0.late_deliveries, 0) + coalesce(u1.late_deliveries, 0) + coalesce(u2.late_deliveries, 0) AS late3,
    coalesce(u0.ratings_count, 0) + coalesce(u1.ratings_count, 0) + coalesce(u2.ratings_count, 0) AS rated3,
    coalesce(u0.ratings_sum, 0) + coalesce(u1.ratings_sum, 0) + coalesce(u2.ratings_sum, 0) AS stars3,
    (
        SELECT count(*) FROM tickets AS t
        WHERE t.customer_id = b.customer_id AND t.created < b.cut AND t.created >= b.cut - INTERVAL 90 DAY
    ) AS tickets_90d,
    (
        SELECT count(*) FROM tickets AS t
        WHERE t.customer_id = b.customer_id AND t.created < b.cut AND (t.resolved IS NULL OR t.resolved >= b.cut)
    ) AS open_tickets,
    (
        SELECT count(*) FROM invoices AS i
        WHERE
            i.customer_id = b.customer_id AND i.kind = 'charge' AND i.status = 'failed'
            AND i.month BETWEEN b.snap_month - 2 AND b.snap_month
    ) AS failed_payments_3m
FROM snapshot_base AS b
LEFT JOIN paid AS nxt ON b.customer_id = nxt.customer_id AND nxt.month = b.snap_month + 1
LEFT JOIN paid AS prv ON b.customer_id = prv.customer_id AND prv.month = b.snap_month - 1
LEFT JOIN usage AS u0 ON b.customer_id = u0.customer_id AND u0.month = b.snap_month
LEFT JOIN usage AS u1 ON b.customer_id = u1.customer_id AND u1.month = b.snap_month - 1
LEFT JOIN usage AS u2 ON b.customer_id = u2.customer_id AND u2.month = b.snap_month - 2;

CREATE OR REPLACE TABLE features AS
SELECT
    customer_id,
    snapshot,
    split,
    CAST(substr(customer_id, 2) AS INTEGER) % getvariable('folds') AS fold,
    churned,
    CAST(tenure AS DOUBLE) AS tenure_months,
    CAST(tenure < 3 AS DOUBLE) AS is_new,
    CAST(plan = 'standard' AS DOUBLE) AS plan_standard,
    CAST(plan = 'premium' AS DOUBLE) AS plan_premium,
    discount / list_price AS discount_share,
    coalesce((list_price - prev_price) / prev_price, 0.0) AS price_change_pct,
    CAST(meals0 AS DOUBLE) AS meals_last_month,
    CASE WHEN meals0 + skipped0 > 0 THEN skipped0 / (meals0 + skipped0) ELSE 0.0 END AS skip_rate_last_month,
    CASE
        WHEN least(tenure, 2) > 0
            THEN
                meals0
                - (CASE WHEN tenure >= 1 THEN meals1 ELSE 0 END + CASE WHEN tenure >= 2 THEN meals2 ELSE 0 END)
                / least(tenure, 2)
        ELSE 0.0
    END AS meals_trend,
    CASE WHEN meals0 + meals1 + meals2 > 0 THEN late3 / (meals0 + meals1 + meals2) ELSE 0.0 END AS late_rate_3m,
    CASE WHEN rated3 > 0 THEN stars3 / rated3 ELSE getvariable('rating_default') END AS avg_rating_3m,
    CAST(rated3 = 0 AS DOUBLE) AS rating_missing,
    CAST(tickets_90d AS DOUBLE) AS tickets_90d,
    CAST(open_tickets AS DOUBLE) AS open_tickets,
    CAST(failed_payments_3m AS DOUBLE) AS failed_payments_3m,
    city,
    city_tier,
    age_band,
    acquisition_channel AS channel,
    plan,
    list_price AS price_inr
FROM snapshot_inputs
ORDER BY snapshot, customer_id;

-- one row per snapshot: the contract checks snapshots.rows.min and snapshots.churn_rate.range read this table
CREATE OR REPLACE TABLE snapshots AS
SELECT
    snapshot,
    any_value(split) AS split,
    count(*) AS rows,
    CASE WHEN count(churned) = count(*) THEN sum(churned) END AS churned,
    CASE WHEN count(churned) = count(*) THEN sum(churned) / count(*) END AS churn_rate
FROM features
GROUP BY snapshot
ORDER BY snapshot;

-- the features in long form (one row per customer, snapshot and feature), for the rules, scoring and scans
CREATE OR REPLACE TABLE feature_long AS
UNPIVOT (
    SELECT * EXCLUDE (city, city_tier, age_band, channel, plan, price_inr) FROM features
)
ON COLUMNS(* EXCLUDE (customer_id, snapshot, split, fold, churned))
INTO NAME feature VALUE value;
