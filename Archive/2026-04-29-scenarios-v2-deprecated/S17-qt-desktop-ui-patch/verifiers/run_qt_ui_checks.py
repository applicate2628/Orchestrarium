#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S17 Qt UI bundle shape, start state, or a completed candidate run."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S17 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract and metadata.",
    )
    parser.add_argument(
        "--expect-start-state",
        action="store_true",
        help="Validate that the bundled candidate root still exhibits the intended failures.",
    )
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_simple_yaml(path: Path):
    data = {}
    current_list = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_list is None:
                raise ValueError(f"Unexpected list item in {path}: {line}")
            data[current_list].append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value == "":
            data[key] = []
            current_list = key
        elif value == "[]":
            data[key] = []
            current_list = None
        else:
            data[key] = value.strip('"')
            current_list = None
    return data


def top_level_yaml_keys(path: Path):
    keys = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        keys.append(line.split(":", 1)[0].strip())
    return keys


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def import_candidate_module(bundle_root: Path):
    src_root = bundle_root / "candidate" / "qt-settings-dialog" / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))
    importlib.invalidate_caches()
    for name in [
        "qt_settings_dialog.rename_preset_dialog",
        "qt_settings_dialog",
    ]:
        sys.modules.pop(name, None)
    return importlib.import_module("qt_settings_dialog.rename_preset_dialog")


def build_tab_chain(dialog, steps=4):
    chain = []
    current = dialog.name_edit
    seen = set()
    while current is not None and current not in seen and len(chain) < steps:
        chain.append(current.objectName())
        seen.add(current)
        current = dialog.tab_successor(current)
    return chain


def evaluate_cases(bundle_root: Path):
    oracle = load_json(bundle_root / "oracle" / "interaction-oracle.json")
    module = import_candidate_module(bundle_root)
    dialog = module.RenamePresetDialog()
    failures = []

    focus_widget = dialog.focusWidget()
    if focus_widget is None or focus_widget.objectName() != oracle["required_start_focus"]:
        failures.append("initial-focus")

    if dialog.error_label.focusPolicy() != getattr(module.Qt, oracle["required_error_focus_policy"]):
        failures.append("error-label-focus-policy")

    if build_tab_chain(dialog, steps=len(oracle["required_tab_chain"])) != oracle["required_tab_chain"]:
        failures.append("tab-order")

    dialog.save_button.setFocus()
    dialog.name_edit.setText("   ")
    if dialog.save_button.isEnabled() != oracle["blank_name_save_enabled"]:
        failures.append("blank-name-save-enabled")
    if dialog.error_label.isVisible() != oracle["blank_name_error_visible"]:
        failures.append("blank-name-error-visible")
    focus_widget = dialog.focusWidget()
    if focus_widget is None or focus_widget.objectName() != oracle["blank_name_focus_target"]:
        failures.append("blank-name-focus-recovery")

    dialog.reset_result()
    dialog.name_edit.setFocus()
    dialog.press_key(module.Qt.Key_Return)
    if oracle["return_accept_requires_valid_name"] and dialog.accepted:
        failures.append("return-accepts-invalid")

    dialog.reset_result()
    dialog.press_key(module.Qt.Key_Escape)
    if oracle["escape_rejects"] and not dialog.rejected:
        failures.append("escape-does-not-reject")

    dialog.prepare_for_reopen("Weekend Plan")
    if oracle["reopen_requires_result_reset"] and (dialog.accepted or dialog.rejected):
        failures.append("reopen-lifecycle")
    focus_widget = dialog.focusWidget()
    if focus_widget is None or focus_widget.objectName() != oracle["reopen_focus_target"]:
        failures.append("reopen-lifecycle")
    if dialog.error_label.isVisible() != oracle["reopen_error_visible"]:
        failures.append("reopen-error-state")
    if dialog.save_button.isEnabled() != oracle["valid_reopen_save_enabled"]:
        failures.append("reopen-save-enabled")

    return sorted(set(failures))


def run_direct_tests(bundle_root: Path, errors):
    candidate_root = bundle_root / "candidate" / "qt-settings-dialog"
    test_path = candidate_root / "tests" / "test_rename_preset_dialog.py"
    try:
        result = subprocess.run(
            [sys.executable, str(test_path)],
            cwd=candidate_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        errors.append(f"Unable to run direct Qt UI tests: {exc}")
        return

    combined_output = "\n".join(
        part for part in [result.stdout.strip(), result.stderr.strip()] if part
    ).strip()
    require(
        result.returncode == 0,
        f"Direct Qt UI tests failed: {combined_output or 'no output'}",
        errors,
    )


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

    for entry in contract["required_bundle_files"]:
        require((bundle_root / entry).exists(), f"Missing bundle file: {entry}", errors)

    scenario_path = bundle_root / "scenario.yaml"
    require(scenario_path.exists(), "Missing scenario.yaml", errors)
    if not scenario_path.exists():
        return

    keys = top_level_yaml_keys(scenario_path)
    require(
        keys == contract["scenario_yaml_fields"],
        "scenario.yaml fields do not match the required contract order exactly",
        errors,
    )

    metadata = parse_simple_yaml(scenario_path)
    require(metadata == contract["expected_metadata"], "scenario.yaml metadata does not match S17", errors)

    for path_str in contract["required_candidate_paths"]:
        require((bundle_root / path_str).exists(), f"Missing required candidate path: {path_str}", errors)


def check_start_state(bundle_root: Path, contract, errors):
    actual = evaluate_cases(bundle_root)
    expected = sorted(contract["expected_start_state_failures"])
    require(actual == expected, f"Expected start-state failures {expected}, found {actual}", errors)


def check_completed_run(bundle_root: Path, errors):
    actual = evaluate_cases(bundle_root)
    require(not actual, f"Completed candidate still fails oracle cases: {actual}", errors)
    if not errors:
        run_direct_tests(bundle_root, errors)


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    errors = []

    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    contract = load_json(bundle_root / "oracle" / "qt-ui-contract.json")
    check_bundle_shape(bundle_root, contract, errors)

    if not args.bundle_shape_only:
        if args.expect_start_state:
            check_start_state(bundle_root, contract, errors)
        else:
            check_completed_run(bundle_root, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        mode = "bundle shape"
    elif args.expect_start_state:
        mode = "start state"
    else:
        mode = "completed run"

    print(f"S17 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
