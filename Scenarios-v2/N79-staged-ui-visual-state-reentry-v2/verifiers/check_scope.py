#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_contract(root: Path):
    return json.loads((root / "oracle" / "ui-visual-state-contract.json").read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Check N79 exact changed-path budget.")
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
        errors.append(f"Changed paths outside exact N79 UI/visual patch budget: {extra}")

    if errors:
        print("N79 scope FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("N79 scope PASS")


if __name__ == "__main__":
    main()
