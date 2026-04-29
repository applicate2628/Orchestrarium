#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate that S18 changed paths stay inside the declared allowed change surface."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root)
    parser.add_argument("--changed-path", action="append", default=[])
    return parser.parse_args()


def parse_allowed_surface(path: Path):
    allowed = []
    current_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current_key == "allowed_change_surface":
            allowed.append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        current_key = line.split(":", 1)[0].strip()
    return allowed


def main():
    args = parse_args()
    scenario_path = args.bundle_root.resolve() / "scenario.yaml"
    if not scenario_path.exists():
        print(f"Missing scenario.yaml at {scenario_path}", file=sys.stderr)
        return 1

    allowed = parse_allowed_surface(scenario_path)
    if len(allowed) != 2:
        print("ERROR: S18 expected exactly two allowed change paths", file=sys.stderr)
        return 1
    if not all(path.startswith("candidate/model-view-owned/") for path in allowed):
        print("ERROR: Allowed change surface escapes the model-view-owned root", file=sys.stderr)
        return 1

    unexpected = [path for path in args.changed_path if path not in allowed]
    if unexpected:
        for path in unexpected:
            print(f"ERROR: Changed path is out of scope: {path}", file=sys.stderr)
        return 1

    if args.changed_path:
        print("S18 scope PASS (changed paths are in bounds)")
    else:
        print("S18 scope PASS (manifest is model-view-owned only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
