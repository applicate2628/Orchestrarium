#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check N50 changed paths stay in immutable-CI compact operator-budget scope.")
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

    protected = contract.get("protected_file_hashes", {})
    for rel_path, expected_hash in protected.items():
        file_path = root / rel_path
        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            print(f"ERROR: protected immutable-CI file changed: {rel_path}", file=sys.stderr)
            return 1

    if args.changed_paths and not any(path.startswith("candidate/workspace/src/stagegate/") for path in args.changed_paths):
        print("ERROR: no production stagegate implementation file changed", file=sys.stderr)
        return 1

    print("N50 scope PASS (immutable-CI changed paths are in bounds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
