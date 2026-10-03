-- failing rows = {column} has no matching customer_id in {to_table}
SELECT
    count(*) FILTER (WHERE {column} NOT IN (SELECT t.customer_id FROM {to_table} AS t)) AS failing_rows,
    count(*) AS checked_rows
FROM {table}
