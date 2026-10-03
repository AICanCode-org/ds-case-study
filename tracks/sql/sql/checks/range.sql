-- failing rows = a known {column} value outside [{min}, {max}] (NULL means "not known", e.g. an unlabelled month)
SELECT
    count(*) FILTER (WHERE {column} < {min} OR {column} > {max}) AS failing_rows,
    count({column}) AS checked_rows
FROM {table}
