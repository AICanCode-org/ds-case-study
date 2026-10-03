-- failing rows = rows whose {column} value appears more than once
SELECT
    count(*) - count(DISTINCT ({column})) AS failing_rows,
    count(*) AS checked_rows
FROM {table}
