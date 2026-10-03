-- failing rows = a known {column} value outside [{min}, {max}] (NULL means "not known", e.g. an unlabelled month)
-- TODO(M2): one row (failing_rows, checked_rows); {table} and {column} come from the contract
SELECT
    NULL AS failing_rows,
    NULL AS checked_rows
