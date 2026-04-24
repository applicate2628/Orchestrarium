#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check N44 changed paths stay in scope.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = json.loads((root / "oracle" / "interface-refactor-contract.json").read_text(encoding="utf-8"))
    allowed = set(contract["expected_metadata"]["allowed_change_surface"])
    unexpected = sorted(path for path in args.changed_paths if path not in allowed)
    if unexpected:
        for path in unexpected:
            print(f"ERROR: changed path outside allowed surface: {path}", file=sys.stderr)
        return 1

    for rel_path, expected_hash in contract.get("protected_file_hashes", {}).items():
        path = root / rel_path
        if not path.exists():
            print(f"ERROR: protected file missing: {rel_path}", file=sys.stderr)
            return 1
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            print(f"ERROR: protected file modified: {rel_path}", file=sys.stderr)
            print(f"Actual hash: {actual_hash}", file=sys.stderr)
            print(f"Expected hash: {expected_hash}", file=sys.stderr)
            return 1

    try:
        ledger = json.loads((root / "candidate" / "refactor-ledger.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: candidate/refactor-ledger.json is not valid JSON: {exc}", file=sys.stderr)
        return 1

    budget = ledger.get("patchBudget", {})
    required = sorted(budget.get("requiredChangedPaths", []))
    actual = sorted(args.changed_paths)
    if budget.get("maxChangedPaths") != len(contract["requiredChangedPaths"]):
        print("ERROR: patchBudget.maxChangedPaths must match N44 required path count", file=sys.stderr)
        return 1
    if actual != required:
        print("ERROR: actual changed paths must exactly match patchBudget.requiredChangedPaths", file=sys.stderr)
        print(f"Actual: {actual}", file=sys.stderr)
        print(f"Required: {required}", file=sys.stderr)
        return 1

    print("N44 scope PASS (changed paths are in bounds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
