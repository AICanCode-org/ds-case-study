-- M3 · Snapshots, labels and point-in-time features (contract/feature-spec.md §3-§4).
-- A snapshot is the end of month M; the cut-off S is the first instant of month M+1. A feature may use invoices
-- and usage of months <= M, tickets created before S and resolutions before S. The label looks at M+1 only.
-- The runner fills cfg_snapshots (month index, label, split) with the contract snapshots the export covers and
-- sets the variables export_month, rating_default and folds.

-- TODO(M3) paid: contract/feature-spec.md §3-§4; tests: tests/unit/test_features.py
CREATE OR REPLACE TABLE paid AS
SELECT NULL AS todo;

-- TODO(M3) snapshot_base: contract/feature-spec.md §3-§4; tests: tests/unit/test_features.py
CREATE OR REPLACE VIEW snapshot_base AS
SELECT NULL AS todo;

-- TODO(M3) snapshot_inputs: contract/feature-spec.md §3-§4; tests: tests/unit/test_features.py
CREATE OR REPLACE VIEW snapshot_inputs AS
SELECT NULL AS todo;

-- TODO(M3) features: contract/feature-spec.md §3-§4; tests: tests/unit/test_features.py
CREATE OR REPLACE TABLE features AS
SELECT NULL AS todo;

-- one row per snapshot: the contract checks snapshots.rows.min and snapshots.churn_rate.range read this table
-- TODO(M3) snapshots: contract/feature-spec.md §3-§4; tests: tests/unit/test_features.py
CREATE OR REPLACE TABLE snapshots AS
SELECT NULL AS todo;

-- the features in long form (one row per customer, snapshot and feature), for the rules, scoring and scans
-- TODO(M3) feature_long: contract/feature-spec.md §3-§4; tests: tests/unit/test_features.py
CREATE OR REPLACE TABLE feature_long AS
SELECT NULL AS todo;
