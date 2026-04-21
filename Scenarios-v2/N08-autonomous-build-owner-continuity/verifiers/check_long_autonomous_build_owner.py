#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


EXPECTED_METADATA = {
    "id": "N08",
    "surface_id": "E1",
    "pack_id": "E1",
    "role_class": "overlay worker",
    "artifact_type": "autonomous implementation patch plus validation",
    "modality_family": "long autonomous build-owner continuity",
    "allowed_change_surface": [
        "candidate/workspace/src/path/findOwnedTarget.js",
        "candidate/workspace/src/workspace/findWorkspaceRoot.js",
    ],
    "must_not_touch": [
        "inputs/**",
        "oracle/**",
        "verifiers/**",
        "candidate/README.md",
        "candidate/scripts/**",
        "candidate/docs/**",
        "candidate/legacy/**",
        "candidate/workspace-shadow/**",
        "candidate/workspace/vendor/**",
        "candidate/workspace/src/routing/**",
        "candidate/workspace/src/toolchain/**",
        "candidate/workspace/scripts/**",
        "candidate/workspace/test/**",
    ],
    "score_profile": "implementation, long-autonomous",
    "overlay_flags": ["long-autonomous"],
}


REQUIRED_PATHS = [
    "README.md",
    "scenario.yaml",
    "candidate/README.md",
    "candidate/workspace/package.json",
    "candidate/workspace/src/runContinuityWorkerTask.js",
    "candidate/workspace/src/path/findOwnedTarget.js",
    "candidate/workspace/src/workspace/findWorkspaceRoot.js",
    "candidate/workspace/scripts/verify-build.js",
    "candidate/workspace/test/runContinuityWorkerTask.test.js",
    "candidate/scripts/findOwnedTarget.js",
    "candidate/docs/notes/lanePriorityResolver.js",
    "candidate/legacy/lanePriorityResolver.js",
    "candidate/workspace-shadow/package.json",
    "inputs/task.md",
    "oracle/scoring-anchors.md",
    "verifiers/check_scope.py",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N08 bundle or completed candidate.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    return parser.parse_args()


def parse_simple_yaml(path: Path):
    data = {}
    current_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            data.setdefault(current_key, []).append(line[4:].strip())
            continue
        if ":" not in line or line.startswith(" "):
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value == "":
            data[key] = []
            current_key = key
        elif value == "[]":
            data[key] = []
            current_key = None
        else:
            data[key] = value.strip('"')
            current_key = None
    return data


def run_command(workspace: Path, args: list[str]):
    return subprocess.run(args, cwd=workspace, capture_output=True, text=True, check=False)


def command_output(result: subprocess.CompletedProcess[str]):
    return "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()


def require(condition: bool, message: str, errors: list[str]):
    if not condition:
        errors.append(message)


def check_shape(root: Path, errors: list[str]):
    require(sorted(p.name for p in root.iterdir()) == ["README.md", "candidate", "inputs", "oracle", "scenario.yaml", "verifiers"], "Top-level bundle entries drifted", errors)
    require(parse_simple_yaml(root / "scenario.yaml") == EXPECTED_METADATA, "scenario.yaml metadata does not match N08", errors)
    for path in REQUIRED_PATHS:
        require((root / path).exists(), f"Missing required path: {path}", errors)


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list[str] = []
    check_shape(root, errors)

    if not args.bundle_shape_only:
        workspace = root / "candidate" / "workspace"
        test_result = run_command(workspace, ["node", "--test"])
        verify_result = run_command(workspace, ["node", "scripts/verify-build.js"])
        if args.expect_start_state:
            require(test_result.returncode != 0, "Expected start-state node --test to fail", errors)
            require(verify_result.returncode != 0, "Expected start-state verify-build to fail", errors)
        else:
            require(test_result.returncode == 0, f"node --test failed: {command_output(test_result)}", errors)
            require(verify_result.returncode == 0, f"verify-build failed: {command_output(verify_result)}", errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "start state" if args.expect_start_state else "completed run"
    print(f"N08 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
