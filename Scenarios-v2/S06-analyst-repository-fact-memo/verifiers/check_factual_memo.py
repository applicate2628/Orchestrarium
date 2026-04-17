#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S06 analyst bundle shape or a completed factual memo."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S06 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "fact-contract.json"
    return json.loads(contract_path.read_text(encoding="utf-8"))


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


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

    for relative_path in contract["required_bundle_paths"]:
        require(
            (bundle_root / relative_path).exists(),
            f"Missing required bundle path: {relative_path}",
            errors,
        )

    scenario_path = bundle_root / "scenario.yaml"
    require(scenario_path.exists(), "Missing scenario.yaml", errors)
    if scenario_path.exists():
        keys = top_level_yaml_keys(scenario_path)
        require(
            keys == contract["scenario_yaml_fields"],
            "scenario.yaml fields do not match the required contract order exactly",
            errors,
        )


def unique_repo_references(text: str):
    return set(re.findall(r"candidate/repo-snapshot/[A-Za-z0-9_./-]+:\d+", text))


def check_completed_memo(bundle_root: Path, contract, errors):
    memo_path = bundle_root / contract["editable_memo"]
    require(memo_path.exists(), f"Missing candidate file: {contract['editable_memo']}", errors)
    if errors:
        return

    text = memo_path.read_text(encoding="utf-8")

    for section in contract["required_memo_sections"]:
        require(section in text, f"Missing memo section: {section}", errors)

    for marker in contract["disallowed_markers"]:
        require(marker not in text, f"Disallowed marker present in memo: {marker}", errors)

    for heading in contract["disallowed_headings"]:
        require(heading not in text, f"Disallowed role-drift heading present: {heading}", errors)

    references = unique_repo_references(text)
    require(
        len(references) >= contract["minimum_repo_references"],
        "Memo does not contain enough repo-snapshot file references with line numbers",
        errors,
    )

    for anchor in contract["required_reference_anchors"]:
        pattern = rf"{re.escape(anchor)}:\d+"
        require(
            re.search(pattern, text) is not None,
            f"Memo is missing required file-and-line anchor for: {anchor}",
            errors,
        )

    for term in contract["required_false_lead_terms"]:
        require(term in text, f"Memo does not discuss false lead: {term}", errors)

    for term in contract["required_unknown_terms"]:
        require(term in text, f"Memo is missing required unknown anchor: {term}", errors)

    require(
        re.search(r"(?m)^PASS$", text) is not None,
        f"Memo does not contain gate decision {contract['expected_gate_decision']}",
        errors,
    )


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    errors = []

    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    contract = load_contract(bundle_root)
    check_bundle_shape(bundle_root, contract, errors)
    if not args.bundle_shape_only:
        check_completed_memo(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed factual memo"
    print(f"S06 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
