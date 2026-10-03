"""M1 · Load the raw export as text: no type guessing, empty strings stay empty strings."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_raw(data_dir: str | Path, contract: dict) -> dict[str, pd.DataFrame]:
    # TODO(M1) load_raw: read every CSV as TEXT (no type guessing; an empty cell stays an empty string); a
    # missing file or column is a contract error (exit 3). Spec: contract/feature-spec.md §1-§2; tests: load.
    raise NotImplementedError("TODO(M1) load_raw: see the comment above")


def load_export_meta(data_dir: str | Path) -> dict:
    # TODO(M1) load_export_meta: export.json names the export month; every snapshot and label depends on it.
    # Spec: contract/feature-spec.md §1-§2; tests: load.
    raise NotImplementedError("TODO(M1) load_export_meta: see the comment above")
