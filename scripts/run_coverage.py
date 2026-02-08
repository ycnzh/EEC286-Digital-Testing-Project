from __future__ import annotations

import argparse
import os
from pathlib import Path

from .fault_injector import run_coverage_once


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--circuit", required=True, help="e.g., c17")
    ap.add_argument("--vectors", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--fault-file", default="", help="expanded fault list file (optional)")
    ap.add_argument("--verilog-dir", default="circuits/verilog", help="default: circuits/verilog")
    ap.add_argument("--tb-dir", default="tb", help="default: tb")
    ap.add_argument("--csv", default="", help="write/append results to csv")
    args = ap.parse_args()

    project_root = Path(os.getcwd())  # assume you run from repo root
    verilog_path = project_root / args.verilog_dir / f"{args.circuit}.v"
    if not verilog_path.exists():
        raise FileNotFoundError(f"Cannot find verilog: {verilog_path}")

    fault_file = args.fault_file.strip() or None
    if fault_file:
        ff = Path(fault_file)
        if not ff.is_absolute():
            ff = project_root / ff
        if not ff.exists():
            raise FileNotFoundError(f"Cannot find fault file: {ff}")
        fault_file = str(ff)

    csv_path = args.csv.strip() or None
    if csv_path:
        cp = Path(csv_path)
        if not cp.is_absolute():
            cp = project_root / cp
        csv_path = str(cp)

    res = run_coverage_once(
        circuit=args.circuit,
        verilog_path=str(verilog_path),
        tb_dir=str(project_root / args.tb_dir),
        vectors_n=args.vectors,
        seed=args.seed,
        fault_file=fault_file,
        csv_path=csv_path,
    )

    print(
        f"[OK] {res['circuit']} vectors={res['vectors']} "
        f"faults={res['faults']} unique_detected={res['unique_detected']} "
        f"coverage={res['coverage']:.4f} seed={res['seed']}"
    )


if __name__ == "__main__":
    main()
