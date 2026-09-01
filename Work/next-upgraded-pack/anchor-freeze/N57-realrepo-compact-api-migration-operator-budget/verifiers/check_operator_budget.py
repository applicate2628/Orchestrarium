#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check N57 visible operator-output budget.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract_path = root / "oracle" / "compact-api-contract.json"
    if not contract_path.exists():
        print(f"ERROR: missing contract: {contract_path}", file=sys.stderr)
        return 1

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    budget = contract.get("operator_budget", {})
    max_bytes = int(budget.get("max_worker_output_bytes", 0))
    if max_bytes <= 0:
        print("ERROR: operator_budget.max_worker_output_bytes is missing or invalid", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        print("N57 operator-budget PASS (bundle shape)")
        return 0

    worker_output = root.parent / "meta" / "worker-output.txt"
    if not worker_output.exists():
        print(f"ERROR: missing worker output for operator budget: {worker_output}", file=sys.stderr)
        return 1

    actual = worker_output.stat().st_size
    if actual > max_bytes:
        print(f"ERROR: operator output budget exceeded: {actual} > {max_bytes} bytes", file=sys.stderr)
        return 1

    print(f"N57 operator-budget PASS ({actual} <= {max_bytes} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
