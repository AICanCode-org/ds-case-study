-- failing rows = {column} is NULL or blank
SELECT
    count(*) FILTER (WHERE {column} IS NULL OR trim(CAST({column} AS VARCHAR)) = '') AS failing_rows,
    count(*) AS checked_rows
FROM {table}
