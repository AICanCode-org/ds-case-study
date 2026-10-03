-- failing rows = {column} equals the check's value (in cfg_check_values); the check fails when their share > max
-- TODO(M2): one row (failing_rows, checked_rows); {table} and {column} come from the contract
SELECT
    NULL AS failing_rows,
    NULL AS checked_rows
