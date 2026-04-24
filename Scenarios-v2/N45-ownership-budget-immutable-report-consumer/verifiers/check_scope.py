#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check N45 changed paths stay in scope.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = json.loads((root / "oracle" / "ownership-budget-contract.json").read_text(encoding="utf-8"))
    filtered_paths = [
        path
        for path in args.changed_paths
        if not (
            path == ".pytest_cache"
            or path.startswith(".pytest_cache/")
            or path == ".mypy_cache"
            or path.startswith(".mypy_cache/")
            or "/__pycache__/" in path
            or path.endswith(".pyc")
        )
    ]
    for rel_path, expected_hash in contract.get("protected_file_hashes", {}).items():
        protected = root / rel_path
        if not protected.exists():
            print(f"ERROR: protected file missing: {rel_path}", file=sys.stderr)
            return 1
        actual_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
        if actual_hash.lower() != expected_hash.lower():
            print(f"ERROR: protected file hash changed: {rel_path}", file=sys.stderr)
            return 1
    allowed = set(contract["expected_metadata"]["allowed_change_surface"])
    unexpected = sorted(path for path in filtered_paths if path not in allowed)
    if unexpected:
        for path in unexpected:
            print(f"ERROR: changed path outside allowed surface: {path}", file=sys.stderr)
        return 1
    try:
        repair_ledger = json.loads((root / "candidate" / "repair-ledger.json").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: candidate/repair-ledger.json is not valid JSON: {exc}", file=sys.stderr)
        return 1
    budget = repair_ledger.get("patchBudget", {})
    required = sorted(budget.get("requiredChangedPaths", []))
    actual = sorted(filtered_paths)
    if budget.get("maxChangedPaths") != 3:
        print("ERROR: patchBudget.maxChangedPaths must be 3", file=sys.stderr)
        return 1
    expected_required = sorted(contract["required_changed_paths"])
    if required != expected_required:
        print("ERROR: patchBudget.requiredChangedPaths must match the N45 required production/ledger paths", file=sys.stderr)
        print(f"Required: {required}", file=sys.stderr)
        print(f"Expected: {expected_required}", file=sys.stderr)
        return 1
    if actual != required:
        print("ERROR: actual changed paths must exactly match patchBudget.requiredChangedPaths", file=sys.stderr)
        print(f"Actual: {actual}", file=sys.stderr)
        print(f"Required: {required}", file=sys.stderr)
        return 1
    if len(actual) > budget["maxChangedPaths"]:
        print(f"ERROR: changed path count exceeds patch budget: {len(actual)} > {budget['maxChangedPaths']}", file=sys.stderr)
        return 1
    print("N45 scope PASS (changed paths are in bounds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
