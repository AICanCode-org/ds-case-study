"""M2 · The contract checks (contract/data-contract.yaml `checks`): one result per check, in contract order.
A failing check with severity `error` stops the run (exit code 3): a model trained on a broken export is worse than
no model."""

from __future__ import annotations

import pandas as pd


def _values(table: pd.DataFrame, column) -> pd.Series:
    # TODO(M2) _values: the column(s) a check looks at (a list of columns means a composite key). Spec:
    # contract/feature-spec.md §2 and contract/data-contract.yaml `checks`; tests: checks.
    raise NotImplementedError("TODO(M2) _values: see the comment above")


def failing_rows(check: dict, tables: dict[str, pd.DataFrame]) -> tuple[int, int]:
    """(failing rows, rows checked) for one check."""
    # TODO(M2) failing_rows: one contract check -> (failing rows, checked rows), by type: unique, not_null,
    # accepted_values, range, relationship, max_ratio. Spec: contract/feature-spec.md §2 and
    # contract/data-contract.yaml `checks`; tests: checks.
    raise NotImplementedError("TODO(M2) failing_rows: see the comment above")


def run_check(check: dict, tables: dict[str, pd.DataFrame]) -> dict:
    # TODO(M2) run_check: one check -> {id, severity, status, failing_rows, observed}; status pass, else
    # warn/fail by severity. Spec: contract/feature-spec.md §2 and contract/data-contract.yaml `checks`; tests:
    # checks.
    raise NotImplementedError("TODO(M2) run_check: see the comment above")


def run_checks(contract: dict, tables: dict[str, pd.DataFrame], only: set[str] | None = None) -> list[dict]:
    # TODO(M2) run_checks: every check of contract/data-contract.yaml for the given tables, in contract order.
    # Spec: contract/feature-spec.md §2 and contract/data-contract.yaml `checks`; tests: checks.
    raise NotImplementedError("TODO(M2) run_checks: see the comment above")


def raise_on_errors(results: list[dict]) -> None:
    # TODO(M2) raise_on_errors: a failing `error` check stops the run with a contract error (exit 3): no model
    # is better than a model trained on a broken export. Spec: contract/feature-spec.md §2 and
    # contract/data-contract.yaml `checks`; tests: checks.
    raise NotImplementedError("TODO(M2) raise_on_errors: see the comment above")
