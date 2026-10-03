-- failing rows = {column} is not one of the check's values (the runner loads them into cfg_check_values)
-- TODO(M2): one row (failing_rows, checked_rows); {table} and {column} come from the contract
SELECT
    NULL AS failing_rows,
    NULL AS checked_rows
