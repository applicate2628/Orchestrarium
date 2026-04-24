#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check N51 prompt-to-worker-output turnaround budget.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract_path = root / "oracle" / "toolchain-staging-contract.json"
    if not contract_path.exists():
        print(f"ERROR: missing contract: {contract_path}", file=sys.stderr)
        return 1

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    budget = contract.get("turnaround_budget", {})
    max_seconds = float(budget.get("max_prompt_to_worker_output_seconds", 0))
    if max_seconds <= 0:
        print("ERROR: turnaround_budget.max_prompt_to_worker_output_seconds is missing or invalid", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        print("N51 turnaround-budget PASS (bundle shape)")
        return 0

    meta_root = root.parent / "meta"
    prompt_path = meta_root / "prompt.txt"
    worker_output = meta_root / "worker-output.txt"
    if not prompt_path.exists():
        print(f"ERROR: missing prompt timestamp source: {prompt_path}", file=sys.stderr)
        return 1
    if not worker_output.exists():
        print(f"ERROR: missing worker output timestamp source: {worker_output}", file=sys.stderr)
        return 1

    elapsed = max(0.0, worker_output.stat().st_mtime - prompt_path.stat().st_mtime)
    if elapsed > max_seconds:
        print(f"ERROR: turnaround budget exceeded: {elapsed:.3f} > {max_seconds:.3f} seconds", file=sys.stderr)
        return 1

    print(f"N51 turnaround-budget PASS ({elapsed:.3f} <= {max_seconds:.3f} seconds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
