"""M1 · Load the raw export as text: no type guessing, empty strings stay empty strings."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .contract import ContractError


def load_raw(data_dir: str | Path, contract: dict) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir)
    tables = {}
    for name, spec in contract["files"].items():
        path = data_dir / spec["file"]
        if not path.exists():
            raise ContractError(f"missing file: {spec['file']}")
        df = pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False, encoding="utf-8")
        missing = [c for c in spec["columns"] if c not in df.columns]
        if missing:
            raise ContractError(f"{spec['file']}: missing column(s) {', '.join(missing)}")
        tables[name] = df[spec["columns"]].copy()
    return tables


def load_export_meta(data_dir: str | Path) -> dict:
    path = Path(data_dir) / "export.json"
    if not path.exists():
        raise ContractError("missing file: export.json")
    return json.loads(path.read_text(encoding="utf-8"))
