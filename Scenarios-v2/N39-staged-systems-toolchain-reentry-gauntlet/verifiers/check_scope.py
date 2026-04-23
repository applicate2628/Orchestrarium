#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_contract(root: Path):
    return json.loads((root / "oracle" / "toolchain-staging-contract.json").read_text(encoding="utf-8"))


def evaluate_scope(observed: set[str], contract: dict):
    allowed = set(contract["allowedChangedPaths"])
    required_core = set(contract["requiredChangedCorePaths"])
    any_groups = [set(group) for group in contract.get("requiredChangedAnyOf", [])]

    errors = []
    missing_core = sorted(required_core - observed)
    extra = sorted(observed - allowed)
    if missing_core:
        errors.append(f"Missing required core changed paths: {missing_core}")
    for group in any_groups:
        if not observed & group:
            errors.append(f"Missing required one-of changed paths: {sorted(group)}")
    if extra:
        errors.append(f"Changed paths outside bounded N39 staged toolchain patch surface: {extra}")
    return errors


def main():
    parser = argparse.ArgumentParser(description="Check N39 cumulative changed-path budget.")
    parser.add_argument("--changed-path", action="append", default=[])
    args = parser.parse_args()

    root = Path.cwd()
    contract = load_contract(root)
    observed = {path.replace("\\", "/") for path in args.changed_path}

    errors = evaluate_scope(observed, contract)

    if errors:
        print("N39 scope FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("N39 scope PASS")


if __name__ == "__main__":
    main()
