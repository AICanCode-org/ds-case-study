"""The shared data contract (contract/data-contract.yaml): one file, read by every track."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULT = Path(__file__).resolve().parents[3] / "contract" / "data-contract.yaml"


class ContractError(Exception):
    """The export breaks the data contract: the run must stop (exit code 3)."""


def contract_path() -> Path:
    return Path(os.environ.get("CONTRACT_PATH", DEFAULT))


def load_contract(path: str | Path | None = None) -> dict:
    with open(path or contract_path(), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def feature_names(contract: dict, core_only: bool = False) -> list[str]:
    return [f["name"] for f in contract["features"] if f["core"] or not core_only]
