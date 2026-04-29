#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path


EXPECTED_ALLOWED = {
    "candidate/workspace/src/worker/chooseOwnedTarget.js",
    "candidate/workspace/src/worker/appendPatchStep.js",
    "candidate/workspace/src/worker/preserveVerificationPlan.js",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Validate N10 changed paths stay in scope.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
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
        if ":" in line and not line.startswith(" "):
            current_key = line.split(":", 1)[0].strip()
    return set(allowed)


def main():
    args = parse_args()
    allowed = parse_allowed_surface(args.bundle_root / "scenario.yaml")
    if allowed != EXPECTED_ALLOWED:
        print(f"ERROR: N10 allowed surface drifted: {sorted(allowed)}", file=sys.stderr)
        return 1

    unexpected = [path for path in args.changed_path if path not in EXPECTED_ALLOWED]
    if unexpected:
        for path in unexpected:
            print(f"ERROR: Changed path is out of scope: {path}", file=sys.stderr)
        return 1

    print("N10 scope PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
