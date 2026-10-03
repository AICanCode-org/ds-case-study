-- failing rows = {column} equals the check's value (in cfg_check_values); the check fails when their share > max
SELECT
    count(*) FILTER (
        WHERE coalesce(CAST({column} AS VARCHAR) IN (SELECT v.value FROM cfg_check_values AS v), FALSE)
    ) AS failing_rows,
    count(*) AS checked_rows
FROM {table}
