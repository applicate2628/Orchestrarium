#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S03 consultant bundle shape or a completed advisory memo."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S03 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "consultant-contract.json"
    return json.loads(contract_path.read_text(encoding="utf-8"))


def strip_quotes(value: str):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_yaml(path: Path):
    data = {}
    current_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_key is not None:
                data.setdefault(current_key, []).append(strip_quotes(line[4:].strip()))
            continue
        if line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "[]":
            data[key] = []
            current_key = None
        elif value:
            data[key] = strip_quotes(value)
            current_key = None
        else:
            data[key] = []
            current_key = key
    return data


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


def contains_any(text, alternatives):
    lowered = text.lower()
    return any(option.lower() in lowered for option in alternatives)


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

    for relative_path in contract["required_bundle_files"]:
        require(
            (bundle_root / relative_path).exists(),
            f"Missing required bundle file: {relative_path}",
            errors,
        )

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
    for key, expected_value in contract["required_metadata"].items():
        actual_value = metadata.get(key)
        require(
            actual_value == expected_value,
            f"scenario.yaml field {key!r} does not match the required value",
            errors,
        )


def check_completed_memo(bundle_root: Path, contract, errors):
    memo_path = bundle_root / "candidate" / "advisory-memo.md"
    require(memo_path.exists(), "Missing candidate/advisory-memo.md", errors)
    if errors:
        return

    text = memo_path.read_text(encoding="utf-8")

    for section in contract["required_memo_sections"]:
        require(section in text, f"Missing required section: {section}", errors)

    for heading in contract["required_option_headings"]:
        require(heading in text, f"Missing required option heading: {heading}", errors)

    for exact_line in contract["required_exact_lines"]:
        require(exact_line in text, f"Missing required provenance line: {exact_line}", errors)

    for prefix in contract["required_prefix_lines"]:
        require(
            re.search(rf"(?m)^{re.escape(prefix)}\s+\S+", text) is not None,
            f"Missing required provenance prefix: {prefix}",
            errors,
        )

    require(
        contract["required_recommended_option"] in text,
        "Memo does not recommend the admissible direction",
        errors,
    )

    for alternatives in contract["required_keyword_groups"]:
        require(
            contains_any(text, alternatives),
            f"Memo is missing required keyword coverage from: {alternatives}",
            errors,
        )

    status_pattern = rf"(?ms)^## Advisory status\s+{re.escape(contract['required_advisory_status'])}\s*(?:\n## Continuation prompt|\Z)"
    require(
        re.search(status_pattern, text) is not None,
        "Advisory status section is missing or invalid",
        errors,
    )

    continuation_prefixes = "|".join(
        re.escape(prefix) for prefix in contract["valid_continuation_prefixes"]
    )
    continuation_pattern = rf"(?ms)^## Continuation prompt\s+(?:{continuation_prefixes})\s+\S[\s\S]*\Z"
    require(
        re.search(continuation_pattern, text) is not None,
        "Continuation prompt is missing, invalid, or not at the end of the memo",
        errors,
    )

    for marker in contract["disallowed_markers"]:
        require(marker not in text, f"Disallowed marker present in memo: {marker}", errors)


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

    mode = "bundle shape" if args.bundle_shape_only else "completed consultant memo"
    print(f"S03 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
