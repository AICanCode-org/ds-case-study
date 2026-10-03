-- failing rows = {column} is not one of the check's values (the runner loads them into cfg_check_values)
SELECT
    count(*) FILTER (
        WHERE coalesce(CAST({column} AS VARCHAR) IN (SELECT v.value FROM cfg_check_values AS v), FALSE) = FALSE
    ) AS failing_rows,
    count(*) AS checked_rows
FROM {table}
