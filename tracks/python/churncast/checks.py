"""M2 · The contract checks (contract/data-contract.yaml `checks`): one result per check, in contract order.
A failing check with severity `error` stops the run (exit code 3): a model trained on a broken export is worse than
no model."""

from __future__ import annotations

import pandas as pd

from .contract import ContractError


def _values(table: pd.DataFrame, column) -> pd.Series:
    if isinstance(column, list):
        return table[column].astype(str).agg("|".join, axis=1)
    return table[column]


def failing_rows(check: dict, tables: dict[str, pd.DataFrame]) -> tuple[int, int]:
    """(failing rows, rows checked) for one check."""
    table = tables[check["table"]]
    kind = check["type"]
    if kind == "unique":
        v = _values(table, check["column"])
        return int(len(v) - v.nunique()), len(v)
    v = table[check["column"]]
    if kind == "not_null":
        return int((v.isna() | (v.astype(str).str.strip() == "")).sum()), len(v)
    if kind == "accepted_values":
        return int((~v.astype(str).isin([str(x) for x in check["values"]])).sum()), len(v)
    if kind == "range":
        known = v.dropna()
        num = pd.to_numeric(known, errors="coerce")
        return int((num.isna() | (num < check["min"]) | (num > check["max"])).sum()), len(known)
    if kind == "relationship":
        return int((~v.isin(set(tables[check["to"]]["customer_id"]))).sum()), len(v)
    if kind == "max_ratio":
        return int((v.astype(str) == str(check["value"])).sum()), len(v)
    raise ValueError(f"unknown check type: {kind}")


def run_check(check: dict, tables: dict[str, pd.DataFrame]) -> dict:
    failing, rows = failing_rows(check, tables)
    observed = failing / rows if rows else 0.0
    ok = observed <= check["max"] if check["type"] == "max_ratio" else failing == 0
    status = "pass" if ok else ("fail" if check["severity"] == "error" else "warn")
    return {
        "id": check["id"],
        "severity": check["severity"],
        "status": status,
        "failing_rows": failing,
        "observed": observed,
    }


def run_checks(contract: dict, tables: dict[str, pd.DataFrame], only: set[str] | None = None) -> list[dict]:
    return [run_check(c, tables) for c in contract["checks"] if only is None or c["table"] in only]


def raise_on_errors(results: list[dict]) -> None:
    failed = [r["id"] for r in results if r["status"] == "fail"]
    if failed:
        raise ContractError("contract check(s) failed: " + ", ".join(failed))
