-- M1 · Load: every raw CSV as text, exactly as exported (empty cells become '' rather than NULL).
-- The runner sets the variable data_dir and has already compared each header with the contract.

CREATE OR REPLACE TABLE raw_customers AS
SELECT
    coalesce(customer_id, '') AS customer_id,
    coalesce(signup_date, '') AS signup_date,
    coalesce(city, '') AS city,
    coalesce(acquisition_channel, '') AS acquisition_channel,
    coalesce(age_band, '') AS age_band,
    coalesce(cancellation_reason, '') AS cancellation_reason
FROM read_csv(getvariable('data_dir') || '/customers.csv', header = TRUE, all_varchar = TRUE, delim = ',', quote = '"');

CREATE OR REPLACE TABLE raw_invoices AS
SELECT
    coalesce(invoice_id, '') AS invoice_id,
    coalesce(customer_id, '') AS customer_id,
    coalesce(billing_month, '') AS billing_month,
    coalesce(kind, '') AS kind,
    coalesce(plan, '') AS plan,
    coalesce(list_price, '') AS list_price,
    coalesce(discount, '') AS discount,
    coalesce(status, '') AS status
FROM read_csv(getvariable('data_dir') || '/invoices.csv', header = TRUE, all_varchar = TRUE, delim = ',', quote = '"');

CREATE OR REPLACE TABLE raw_usage AS
SELECT
    coalesce(customer_id, '') AS customer_id,
    coalesce(month, '') AS month,
    coalesce(meals_ordered, '') AS meals_ordered,
    coalesce(meals_skipped, '') AS meals_skipped,
    coalesce(late_deliveries, '') AS late_deliveries,
    coalesce(ratings_count, '') AS ratings_count,
    coalesce(ratings_sum, '') AS ratings_sum
FROM read_csv(getvariable('data_dir') || '/usage.csv', header = TRUE, all_varchar = TRUE, delim = ',', quote = '"');

CREATE OR REPLACE TABLE raw_tickets AS
SELECT
    coalesce(ticket_id, '') AS ticket_id,
    coalesce(customer_id, '') AS customer_id,
    coalesce(created_at, '') AS created_at,
    coalesce(category, '') AS category,
    coalesce(resolved_at, '') AS resolved_at
FROM read_csv(getvariable('data_dir') || '/tickets.csv', header = TRUE, all_varchar = TRUE, delim = ',', quote = '"');
