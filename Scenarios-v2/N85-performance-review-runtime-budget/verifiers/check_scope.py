#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_contract(root: Path) -> dict:
    return json.loads((root / "oracle" / "perf-cache-contract.json").read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Check N85 changed-path and patch-quality budget.")
    parser.add_argument("--bundle-root", type=Path, default=Path.cwd())
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--changed-path", action="append", default=[])
    args = parser.parse_args()

    root = args.bundle_root.resolve()
    contract = load_contract(root)
    if args.bundle_shape_only:
        print("N85 scope PASS (bundle shape)")
        return

    required = set(contract["required_changed_paths"])
    optional = set(contract["optional_changed_paths"])
    ignored_prefixes = tuple(contract.get("ignored_changed_path_prefixes", []))
    observed = {path.replace("\\", "/") for path in args.changed_path}
    observed = {path for path in observed if not any(path.startswith(prefix) for prefix in ignored_prefixes)}

    errors = []
    missing = sorted(required - observed)
    extra = sorted(observed - required - optional)
    if missing:
        errors.append(f"Missing required changed paths: {missing}")
    if extra:
        errors.append(f"Changed paths outside N85 patch-quality budget: {extra}")
    if len(observed) > 7:
        errors.append(f"Too many benchmark changed paths for N85 patch-quality budget: {len(observed)} > 7")

    if errors:
        print("N85 scope FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("N85 scope PASS")


if __name__ == "__main__":
    main()
