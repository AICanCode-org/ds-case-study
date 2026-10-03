-- M1 · Clean: the rules of contract/feature-spec.md §2, in order. Every rule that drops or changes rows is
-- counted in the view issues. Contract lists arrive as the tables cfg_city_aliases and cfg_city_tier;
-- the variable missing_label holds the word for a blank channel or age band ('unknown').

CREATE OR REPLACE MACRO month_index(ym) AS  -- noqa: CP05
    CAST(split_part(trim(ym), '-', 1) AS INTEGER) * 12 + CAST(split_part(trim(ym), '-', 2) AS INTEGER) - 1;

CREATE OR REPLACE MACRO parse_date(v) AS CASE  -- noqa: CP05
    WHEN regexp_full_match(trim(v), '\d{4}-\d{2}-\d{2}') THEN try_strptime(trim(v), '%Y-%m-%d')
    WHEN regexp_full_match(trim(v), '\d{2}/\d{2}/\d{4}') THEN try_strptime(trim(v), '%d/%m/%Y')
END;

CREATE OR REPLACE MACRO parse_ts(v) AS CASE  -- noqa: CP05
    WHEN regexp_full_match(trim(v), '\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}') THEN try_strptime(trim(v), '%Y-%m-%d %H:%M:%S')
    WHEN regexp_full_match(trim(v), '\d{2}/\d{2}/\d{4} \d{2}:\d{2}') THEN try_strptime(trim(v), '%d/%m/%Y %H:%M')
END;

CREATE OR REPLACE MACRO parse_money(v) AS  -- noqa: CP05
    round(try_cast(trim(replace(replace(v, '₹', ''), ',', '')) AS DOUBLE), 2);

-- customers ---------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW c1_dated AS
SELECT
    *,
    parse_date(signup_date) AS signup
FROM raw_customers;

CREATE OR REPLACE VIEW c2_valid AS
SELECT * EXCLUDE (signup), signup FROM c1_dated WHERE signup IS NOT NULL;

CREATE OR REPLACE VIEW c3_distinct AS
SELECT DISTINCT * FROM c2_valid;

CREATE OR REPLACE TABLE customers AS
SELECT
    trim(c.customer_id) AS customer_id,
    strftime(c.signup, '%Y-%m-%d') AS signup_date,
    year(c.signup) * 12 + month(c.signup) - 1 AS signup_month,
    coalesce(a.canonical, lower(trim(c.city))) AS city,
    coalesce(t.tier, getvariable('missing_label')) AS city_tier,
    coalesce(nullif(lower(trim(c.acquisition_channel)), ''), getvariable('missing_label')) AS acquisition_channel,
    coalesce(nullif(lower(trim(c.age_band)), ''), getvariable('missing_label')) AS age_band,
    c.cancellation_reason
FROM c3_distinct AS c
LEFT JOIN cfg_city_aliases AS a ON lower(trim(c.city)) = a.alias
LEFT JOIN cfg_city_tier AS t ON coalesce(a.canonical, lower(trim(c.city))) = t.city;

-- invoices ----------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW i1_distinct AS
SELECT DISTINCT * FROM raw_invoices;

CREATE OR REPLACE TABLE invoices AS
SELECT
    i.invoice_id,
    i.customer_id,
    i.billing_month,
    month_index(i.billing_month) AS month,
    lower(trim(i.kind)) AS kind,
    lower(trim(i.plan)) AS plan,
    parse_money(i.list_price) AS list_price,
    parse_money(i.discount) AS discount,
    lower(trim(i.status)) AS status
FROM i1_distinct AS i
WHERE i.customer_id IN (SELECT c.customer_id FROM customers AS c);

-- usage -------------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW u1_distinct AS
SELECT DISTINCT * FROM raw_usage;

CREATE OR REPLACE VIEW u2_typed AS
SELECT
    customer_id,
    month_index(month) AS month,
    CAST(meals_ordered AS INTEGER) AS meals_ordered,
    CAST(meals_skipped AS INTEGER) AS meals_skipped,
    CAST(late_deliveries AS INTEGER) AS late_deliveries,
    CAST(ratings_count AS INTEGER) AS ratings_count,
    CAST(ratings_sum AS INTEGER) AS ratings_sum
FROM u1_distinct;

CREATE OR REPLACE VIEW u3_non_negative AS
SELECT * FROM u2_typed
WHERE least(meals_ordered, meals_skipped, late_deliveries, ratings_count, ratings_sum) >= 0;

CREATE OR REPLACE TABLE usage AS
SELECT u.* FROM u3_non_negative AS u
WHERE u.customer_id IN (SELECT c.customer_id FROM customers AS c);

-- tickets -----------------------------------------------------------------------------------------
CREATE OR REPLACE VIEW t1_parsed AS
SELECT
    ticket_id,
    customer_id,
    parse_ts(created_at) AS created,
    lower(trim(category)) AS category,
    CASE WHEN trim(resolved_at) <> '' THEN parse_ts(resolved_at) END AS resolved_raw
FROM raw_tickets;

CREATE OR REPLACE VIEW t2_valid AS
SELECT
    * EXCLUDE (resolved_raw),
    CASE WHEN resolved_raw >= created THEN resolved_raw END AS resolved,
    coalesce(resolved_raw < created, FALSE) AS backwards
FROM t1_parsed
WHERE created IS NOT NULL;

CREATE OR REPLACE TABLE tickets AS
SELECT
    t.ticket_id,
    t.customer_id,
    t.created,
    t.category,
    t.resolved
FROM t2_valid AS t
WHERE t.customer_id IN (SELECT c.customer_id FROM customers AS c);

-- the issue counts, in the contract's order --------------------------------------------------------
CREATE OR REPLACE VIEW issues AS
SELECT
    1 AS pos,
    'customers_invalid_signup_date' AS issue,
    (SELECT count(*) FROM raw_customers) - (SELECT count(*) FROM c2_valid) AS n
UNION ALL
SELECT 2, 'customers_exact_duplicates', (SELECT count(*) FROM c2_valid) - (SELECT count(*) FROM c3_distinct)
UNION ALL
SELECT 3, 'customers_channel_missing', (SELECT count(*) FROM c3_distinct WHERE trim(acquisition_channel) = '')
UNION ALL
SELECT 4, 'customers_age_band_missing', (SELECT count(*) FROM c3_distinct WHERE trim(age_band) = '')
UNION ALL
SELECT 5, 'invoices_exact_duplicates', (SELECT count(*) FROM raw_invoices) - (SELECT count(*) FROM i1_distinct)
UNION ALL
SELECT 6, 'invoices_orphans', (SELECT count(*) FROM i1_distinct) - (SELECT count(*) FROM invoices)
UNION ALL
SELECT 7, 'usage_exact_duplicates', (SELECT count(*) FROM raw_usage) - (SELECT count(*) FROM u1_distinct)
UNION ALL
SELECT 8, 'usage_negative_counts', (SELECT count(*) FROM u2_typed) - (SELECT count(*) FROM u3_non_negative)
UNION ALL
SELECT 9, 'usage_orphans', (SELECT count(*) FROM u3_non_negative) - (SELECT count(*) FROM usage)
UNION ALL
SELECT 10, 'tickets_invalid_created_at', (SELECT count(*) FROM t1_parsed WHERE created IS NULL)
UNION ALL
SELECT 11, 'tickets_resolved_before_created', (SELECT count(*) FROM t2_valid WHERE backwards)
UNION ALL
SELECT 12, 'tickets_orphans', (SELECT count(*) FROM t2_valid) - (SELECT count(*) FROM tickets);
