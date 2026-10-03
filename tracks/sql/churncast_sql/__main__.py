"""CLI: python -m churncast_sql run --data ../../data/raw/2026-05 --out out
        python -m churncast_sql report --data ../../data/raw/2026-05 --out out   (out/report.md)

Exit codes: 0 ok (even if the gate fails: the gate is reported, CI enforces it), 2 usage or I/O error,
3 the export breaks the data contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb

from .report import write_report
from .runner import ContractError, analyse, connect, load_contract, write_outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="churncast_sql")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("run", "write out/{features.csv,metrics.json,model.json}"), ("report", "out/report.md")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--data", required=True, help="an export folder, e.g. ../../data/raw/2026-05")
        p.add_argument("--out", default="out")
        p.add_argument("--contract", default=None, help="default: $CONTRACT_PATH or contract/data-contract.yaml")
    args = parser.parse_args(argv)
    if not Path(args.data).is_dir():
        print(f"error: no export folder at {args.data}", file=sys.stderr)
        return 2
    con = connect()
    try:
        contract = load_contract(args.contract)
        result = analyse(con, args.data, contract)
        write_outputs(con, result, contract, args.out)
        if args.command == "report":
            write_report(con, result, Path(args.out) / "report.md")
    except ContractError as exc:
        print(f"contract error: {exc}", file=sys.stderr)
        return 3
    except (OSError, duckdb.IOException) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        con.close()
    m = result["metrics"]
    print(
        f"champion {m['champion']['experiment']}: test AUC {m['test']['auc']:.3f}, Brier {m['test']['brier']:.4f}, "
        f"ECE {m['test']['ece']:.4f}, gate {'PASSED' if m['gate']['passed'] else 'FAILED'} -> {args.out}/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
