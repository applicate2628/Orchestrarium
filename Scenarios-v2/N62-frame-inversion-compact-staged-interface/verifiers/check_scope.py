#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_contract(root):
    return json.loads((root / "oracle" / "staged-interface-contract.json").read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Check N62 cumulative changed-path budget.")
    parser.add_argument("--changed-path", action="append", default=[])
    args = parser.parse_args()

    root = Path.cwd()
    contract = load_contract(root)
    expected = set(contract["requiredChangedPaths"])
    observed = {path.replace("\\", "/") for path in args.changed_path}

    errors = []
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing:
        errors.append(f"Missing required changed paths: {missing}")
    if extra:
        errors.append(f"Changed paths outside exact N62 patch budget: {extra}")

    if errors:
        print("N62 scope FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("N62 scope PASS")


if __name__ == "__main__":
    main()
