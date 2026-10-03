#!/usr/bin/env python3
"""Cross-track parity: do the tracks compute the same features, metrics and model?

    python3 scripts/parity.py contract/golden/metrics-2026-05.json tracks/*/out/metrics.json
    python3 scripts/parity.py contract/golden/model-2026-05.json tracks/*/out/model.json
    python3 scripts/parity.py tracks/python/out/features.csv tracks/sql/out/features.csv tracks/r/out/features.csv

Every file is compared with the first one. The tolerances are part of the contract (feature-spec.md §8):
- features.csv: same columns, same rows in the same order; text exactly equal; numbers to 1e-9 relative
  (1e-12 absolute near zero): the features are plain arithmetic, so every track must get them exactly.
- metrics.json / model.json: integers, strings, booleans, nulls and list lengths identical; floats within
  1e-6 absolute + 1e-6 relative. A model fit is an iterative optimisation (scikit-learn's Newton-Cholesky,
  R's IRLS in glm): both converge to the same maximum-likelihood estimate, but not to the last bit.
`generator` (which track and version wrote the file) is ignored.

    python3 scripts/parity.py --backcompat contract/golden/metrics-2026-05.json out/metrics.json

--backcompat (v1.1): the first file is OLDER. Fields that only the newer file has are allowed (schema changes are
additive) and schema_version / contract_version / model_version may differ; every field of the old file must still
be there with the same value. Standard library only; exit code 1 on any difference, with the path of each one.
"""

from __future__ import annotations

import csv
import json
import math
import sys

JSON_ABS = JSON_REL = 1e-6
CSV_REL, CSV_ABS = 1e-9, 1e-12
IGNORE = {"generator"}
BACKCOMPAT_IGNORE = {"$.schema_version", "$.dataset.contract_version", "$.training.contract_version", "$.model_version"}


def close(a: float, b: float, rel: float, abs_: float) -> bool:
    return math.isclose(a, b, rel_tol=rel, abs_tol=abs_)


def diff_json(a, b, path="$", subset=False):
    if subset and path in BACKCOMPAT_IGNORE:
        return
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None or isinstance(a, str) or isinstance(b, str):
        if a != b or type(a) is not type(b):
            yield f"{path}: {a!r} != {b!r}"
        return
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, int) and isinstance(b, int):
            if a != b:
                yield f"{path}: {a} != {b}"
        elif abs(a - b) > JSON_ABS + JSON_REL * abs(a):
            yield f"{path}: {a!r} != {b!r}"
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if path == "$" and k in IGNORE:
                continue
            if subset and k not in a:
                continue
            if k not in a or k not in b:
                yield f"{path}.{k}: only in {'second' if k in b else 'first'} file"
            else:
                yield from diff_json(a[k], b[k], f"{path}.{k}", subset)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield f"{path}: {len(a)} items != {len(b)} items"
            return
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            yield from diff_json(x, y, f"{path}[{i}]", subset)
        return
    yield f"{path}: {type(a).__name__} != {type(b).__name__}"


def number(text: str):
    try:
        return float(text)
    except ValueError:
        return None


def diff_csv(path_a: str, path_b: str):
    with open(path_a, newline="", encoding="utf-8") as fa, open(path_b, newline="", encoding="utf-8") as fb:
        ra, rb = list(csv.reader(fa)), list(csv.reader(fb))
    if ra[0] != rb[0]:
        yield f"columns differ: {ra[0]} != {rb[0]}"
        return
    if len(ra) != len(rb):
        yield f"{len(ra) - 1} rows != {len(rb) - 1} rows"
        return
    head, shown = ra[0], 0
    for i, (x, y) in enumerate(zip(ra[1:], rb[1:], strict=True), start=1):
        for col, u, v in zip(head, x, y, strict=True):
            if u == v:
                continue
            nu, nv = number(u), number(v)
            if nu is not None and nv is not None and close(nu, nv, CSV_REL, CSV_ABS):
                continue
            if u in ("", "NA") and v in ("", "NA"):
                continue
            yield f"row {i} ({x[0]} {x[1]}) {col}: {u!r} != {v!r}"
            shown += 1
            if shown >= 50:
                yield "... (first 50 differences)"
                return


def load(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main(args: list[str]) -> int:
    subset = "--backcompat" in args
    paths = [p for p in args if p != "--backcompat"]
    if len(paths) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    bad = 0
    for p in paths[1:]:
        if paths[0].endswith(".csv"):
            problems, who = list(diff_csv(paths[0], p)), "features"
        else:
            other = load(p)
            problems = list(diff_json(load(paths[0]), other, subset=subset))
            who = other.get("generator", {}).get("track", "?")
        if problems:
            bad += 1
            print(f"DIFFERENT  {p} ({who}): {len(problems)} difference(s)")
            for line in problems[:30]:
                print("   ", line)
        else:
            print(f"MATCH      {p} ({who})" + (" (backcompat: every old field unchanged)" if subset else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
