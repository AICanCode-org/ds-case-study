-- M1 · Clean: the rules of contract/feature-spec.md §2, in order. Every rule that drops or changes rows is
-- counted in the view issues. Contract lists arrive as the tables cfg_city_aliases and cfg_city_tier;
-- the variable missing_label holds the word for a blank channel or age band ('unknown').

-- TODO(M1) month_index: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE MACRO month_index(ym) AS NULL;  -- noqa: CP05

-- TODO(M1) parse_date: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE MACRO parse_date(v) AS NULL;  -- noqa: CP05

-- TODO(M1) parse_ts: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE MACRO parse_ts(v) AS NULL;  -- noqa: CP05

-- TODO(M1) parse_money: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE MACRO parse_money(v) AS NULL;  -- noqa: CP05

-- customers ---------------------------------------------------------------------------------------
-- TODO(M1) c1_dated: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE VIEW c1_dated AS
SELECT NULL AS todo;

-- TODO(M1) c2_valid: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE VIEW c2_valid AS
SELECT NULL AS todo;

-- TODO(M1) c3_distinct: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE VIEW c3_distinct AS
SELECT NULL AS todo;

-- TODO(M1) customers: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE TABLE customers AS
SELECT NULL AS todo;

-- invoices ----------------------------------------------------------------------------------------
-- TODO(M1) i1_distinct: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE VIEW i1_distinct AS
SELECT NULL AS todo;

-- TODO(M1) invoices: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE TABLE invoices AS
SELECT NULL AS todo;

-- usage -------------------------------------------------------------------------------------------
-- TODO(M1) u1_distinct: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE VIEW u1_distinct AS
SELECT NULL AS todo;

-- TODO(M1) u2_typed: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE VIEW u2_typed AS
SELECT NULL AS todo;

-- TODO(M1) u3_non_negative: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE VIEW u3_non_negative AS
SELECT NULL AS todo;

-- TODO(M1) usage: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE TABLE usage AS
SELECT NULL AS todo;

-- tickets -----------------------------------------------------------------------------------------
-- TODO(M1) t1_parsed: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE VIEW t1_parsed AS
SELECT NULL AS todo;

-- TODO(M1) t2_valid: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE VIEW t2_valid AS
SELECT NULL AS todo;

-- TODO(M1) tickets: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE TABLE tickets AS
SELECT NULL AS todo;

-- the issue counts, in the contract's order --------------------------------------------------------
-- TODO(M1) issues: contract/feature-spec.md §2; tests: tests/unit/test_clean.py
CREATE OR REPLACE VIEW issues AS
SELECT NULL AS todo;
