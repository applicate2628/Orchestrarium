#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_contract(root):
    return json.loads((root / "oracle" / "compact-api-contract.json").read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Check N57 compact changed-path budget.")
    parser.add_argument("--changed-path", action="append", default=[])
    args = parser.parse_args()

    root = Path.cwd()
    contract = load_contract(root)
    expected = set(contract["requiredChangedPaths"])
    ignored_prefixes = tuple(contract.get("ignored_changed_path_prefixes", []))
    observed = {path.replace("\\", "/") for path in args.changed_path}
    observed = {path for path in observed if not any(path.startswith(prefix) for prefix in ignored_prefixes)}

    errors = []
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    if missing:
        errors.append(f"Missing required changed paths: {missing}")
    if extra:
        errors.append(f"Changed paths outside exact N57 patch budget: {extra}")

    if errors:
        print("N57 scope FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("N57 scope PASS")


if __name__ == "__main__":
    main()
