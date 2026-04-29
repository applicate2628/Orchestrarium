#!/usr/bin/env python3

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S21 toolchain bundle shape or a completed candidate repair."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S21 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    parser.add_argument(
        "--changed-path",
        dest="changed_paths",
        action="append",
        default=[],
        help="Relative benchmark path changed during the run; may be repeated.",
    )
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def top_level_yaml_keys(path: Path):
    keys = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key = line.split(":", 1)[0].strip()
        if key:
            keys.append(key)
    return keys


def parse_simple_yaml(path: Path):
    parsed = {}
    current_list_key = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_list_key is None:
                raise ValueError(f"List item without active key in {path}")
            parsed.setdefault(current_list_key, []).append(line[4:])
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_list_key = None
        if value == "":
            parsed[key] = []
            current_list_key = key
        elif value == "[]":
            parsed[key] = []
        else:
            parsed[key] = value.strip('"')

    return parsed


def sha256_path(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def check_changed_paths(changed_paths, allowed_paths, errors):
    allowed = set(allowed_paths)
    unexpected = sorted({path for path in changed_paths if path not in allowed})
    if unexpected:
        errors.append(
            "Changed path outside the allowed change surface: " + ", ".join(unexpected)
        )


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

    for entry in contract["required_bundle_files"]:
        require((bundle_root / entry).exists(), f"Missing bundle file: {entry}", errors)

    scenario_path = bundle_root / "scenario.yaml"
    require(scenario_path.exists(), "Missing scenario.yaml", errors)
    if scenario_path.exists():
        keys = top_level_yaml_keys(scenario_path)
        require(
            keys == contract["scenario_yaml_fields"],
            "scenario.yaml fields do not match the required contract order exactly",
            errors,
        )
        parsed = parse_simple_yaml(scenario_path)
        require(
            parsed == contract["expected_scenario"],
            "scenario.yaml values do not match the accepted S21 contract",
            errors,
        )


def check_protected_candidate_files(bundle_root: Path, contract, errors):
    for relative_path, expected_hash in contract["protected_candidate_hashes"].items():
        path = bundle_root / relative_path
        require(path.exists(), f"Missing protected candidate file: {relative_path}", errors)
        if path.exists():
            actual_hash = sha256_path(path)
            require(
                actual_hash == expected_hash,
                f"Protected candidate file changed outside allowed scope: {relative_path}",
                errors,
            )


def check_completed_candidate(bundle_root: Path, contract, errors):
    workspace_root = bundle_root / "candidate" / "workspace"
    workspace_manifest_path = workspace_root / "package.json"
    plan_path = workspace_root / "toolchain" / "bundle-plan.json"
    package_manifest_path = workspace_root / "packages" / "scenario-bundle" / "package.json"

    for path in (workspace_manifest_path, plan_path, package_manifest_path):
        require(path.exists(), f"Missing editable candidate file: {path.relative_to(bundle_root)}", errors)

    check_protected_candidate_files(bundle_root, contract, errors)
    if errors:
        return

    workspace_manifest = load_json(workspace_manifest_path)
    plan = load_json(plan_path)
    package_manifest = load_json(package_manifest_path)

    script_name = contract["required_workspace_script_name"]
    require(
        workspace_manifest.get("scripts", {}).get(script_name) == contract["required_validation_command"],
        f'package.json script {script_name} does not match the required validation command',
        errors,
    )

    expected_plan = contract["expected_plan"]
    for key in ("packageName", "packageRoot", "outDir"):
        require(plan.get(key) == expected_plan[key], f"bundle-plan.json field {key} is incorrect", errors)
    require(
        plan.get("entrypoints") == expected_plan["entrypoints"],
        "bundle-plan.json entrypoints no longer match the required package contract",
        errors,
    )
    require(
        plan.get("publishFiles") == expected_plan["publishFiles"],
        "bundle-plan.json publishFiles no longer match the required package contract",
        errors,
    )

    expected_manifest = contract["expected_package_manifest"]
    require(
        package_manifest.get("name") == expected_manifest["name"],
        "package manifest name changed unexpectedly",
        errors,
    )
    require(
        package_manifest.get("main") == expected_manifest["main"],
        "package manifest main does not point to the expected dist entry",
        errors,
    )
    require(
        package_manifest.get("bin") == expected_manifest["bin"],
        "package manifest bin does not point to the expected dist entry",
        errors,
    )
    require(
        package_manifest.get("exports") == expected_manifest["exports"],
        "package manifest exports do not match the expected dist contract",
        errors,
    )
    require(
        package_manifest.get("files") == expected_manifest["files"],
        "package manifest files do not match the expected publish list",
        errors,
    )

    editable_text = "\n".join(
        [
            workspace_manifest_path.read_text(encoding="utf-8"),
            plan_path.read_text(encoding="utf-8"),
            package_manifest_path.read_text(encoding="utf-8"),
        ]
    )
    for token in contract["forbidden_tokens_in_editable_files"]:
        require(
            token not in editable_text,
            f"Editable toolchain files still contain forbidden token: {token}",
            errors,
        )

    if errors:
        return

    try:
        result = subprocess.run(
            contract["validation_command_argv"],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        errors.append("Node runtime is not available for the local validation command")
        return

    combined_output = "\n".join(
        part for part in [result.stdout.strip(), result.stderr.strip()] if part
    ).strip()
    require(
        result.returncode == 0,
        f"Local validation command failed: {combined_output or 'no output'}",
        errors,
    )
    if result.returncode == 0:
        require(
            contract["required_validation_output"] in combined_output,
            "Local validation output does not report PASS",
            errors,
        )


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    errors = []

    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    contract = load_json(bundle_root / "oracle" / "toolchain-contract.json")
    check_bundle_shape(bundle_root, contract, errors)
    if args.changed_paths:
        check_changed_paths(args.changed_paths, contract["expected_scenario"]["allowed_change_surface"], errors)
    if not args.bundle_shape_only:
        check_completed_candidate(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed toolchain repair"
    print(f"S21 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
