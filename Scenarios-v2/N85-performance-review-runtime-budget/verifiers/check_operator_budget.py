#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N85 performance-lane operator output budget.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = json.loads((root / "oracle" / "perf-cache-contract.json").read_text(encoding="utf-8"))
    budget = contract.get("operator_budget", {})
    max_bytes = int(budget.get("max_worker_output_bytes", 0))

    if max_bytes <= 0:
        print("ERROR: operator_budget.max_worker_output_bytes must be positive", file=sys.stderr)
        return 1

    task_text = (root / "inputs" / "task.md").read_text(encoding="utf-8")
    if str(max_bytes) not in task_text or "worker-output.txt" not in task_text:
        print("ERROR: task.md must visibly declare the operator output budget", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        print("N85 operator-budget PASS (bundle shape)")
        return 0

    worker_output = root.parent / "meta" / "worker-output.txt"
    if not worker_output.exists():
        print(f"ERROR: missing runner worker output for operator budget: {worker_output}", file=sys.stderr)
        return 1

    size = worker_output.stat().st_size
    if size > max_bytes:
        print(f"ERROR: operator output budget exceeded: {size} bytes > {max_bytes} bytes", file=sys.stderr)
        return 1

    print(f"N85 operator-budget PASS ({size} <= {max_bytes} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
