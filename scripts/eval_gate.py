#!/usr/bin/env python3
"""The evaluation gate: exit 1 unless every gate check in a metrics.json passed (CI runs it for every track).

    python3 scripts/eval_gate.py tracks/python/out/metrics.json

Standard library only. Prints one line per check, so a red CI job says which number is not good enough.
"""

from __future__ import annotations

import json
import sys


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__, file=sys.stderr)
        return 2
    failed = 0
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            m = json.load(fh)
        track = m.get("generator", {}).get("track", "?")
        print(f"gate for {path} ({track}, champion {m['champion']['experiment']})")
        for c in m["gate"]["checks"]:
            mark = "PASS" if c["passed"] else "FAIL"
            print(f"  {mark}  {c['id']:<22} value {c['value']:.4f}  threshold {c['threshold']:.4f}")
        if not m["gate"]["passed"]:
            failed += 1
    print("gate PASSED" if not failed else f"gate FAILED for {failed} file(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
