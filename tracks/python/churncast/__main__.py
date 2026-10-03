"""CLI: python -m churncast run --data ../../data/raw/2026-05 --out out

Exit codes: 0 ok (even if the gate fails: the gate is reported, CI enforces it), 2 usage or I/O error,
3 the export breaks the data contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .contract import ContractError, contract_path, load_contract
from .pipeline import analyse, write_outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="churncast")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="train, evaluate and write out/{features.csv,metrics.json,model.json}")
    run.add_argument("--data", required=True, help="an export folder, e.g. ../../data/raw/2026-05")
    run.add_argument("--out", default="out")
    run.add_argument("--contract", default=None, help="default: $CONTRACT_PATH or contract/data-contract.yaml")
    args = parser.parse_args(argv)
    if not Path(args.data).is_dir():
        print(f"error: no export folder at {args.data}", file=sys.stderr)
        return 2
    try:
        result = analyse(args.data, load_contract(args.contract or contract_path()))
        write_outputs(result, args.out)
    except ContractError as exc:
        print(f"contract error: {exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    m = result["metrics"]
    print(
        f"champion {m['champion']['experiment']}: test AUC {m['test']['auc']:.3f}, Brier {m['test']['brier']:.4f}, "
        f"ECE {m['test']['ece']:.4f}, gate {'PASSED' if m['gate']['passed'] else 'FAILED'} -> {args.out}/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
