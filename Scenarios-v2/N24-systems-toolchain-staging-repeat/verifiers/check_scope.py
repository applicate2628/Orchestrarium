#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check N24 changed paths stay in scope.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = json.loads((root / "oracle" / "toolchain-staging-contract.json").read_text(encoding="utf-8"))
    allowed = set(contract["expected_metadata"]["allowed_change_surface"])
    unexpected = sorted(path for path in args.changed_paths if path not in allowed)
    if unexpected:
        for path in unexpected:
            print(f"ERROR: changed path outside allowed surface: {path}", file=sys.stderr)
        return 1
    print("N24 scope PASS (changed paths are in bounds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
