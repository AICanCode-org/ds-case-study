"""Validate run outputs against the contract schemas.   python3 scripts/validate_outputs.py tracks/*/out
Checks <dir>/metrics.json against contract/metrics.schema.json and <dir>/model.json (and any models/*.json given
as files) against contract/model.schema.json. Exit 1 on the first invalid file, with the JSON path of the error."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

CONTRACT = Path(__file__).resolve().parents[1] / "contract"


def validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(json.loads((CONTRACT / name).read_text(encoding="utf-8")))


def main(args: list[str]) -> int:
    if not args:
        print(__doc__, file=sys.stderr)
        return 2
    metrics, model = validator("metrics.schema.json"), validator("model.schema.json")
    todo = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            todo += [(p / "metrics.json", metrics), (p / "model.json", model)]
        else:
            todo.append((p, model if "model" in p.name or p.parent.name == "models" else metrics))
    bad = 0
    for path, v in todo:
        errors = sorted(v.iter_errors(json.loads(path.read_text(encoding="utf-8"))), key=lambda e: list(e.path))
        if errors:
            bad += 1
            e = errors[0]
            print(f"INVALID {path}: {'/'.join(map(str, e.path)) or '$'}: {e.message}")
        else:
            print(f"valid   {path}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
