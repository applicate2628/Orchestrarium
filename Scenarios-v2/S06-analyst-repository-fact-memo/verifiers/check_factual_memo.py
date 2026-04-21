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


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def extract_section_bodies(markdown_text: str):
    sections = {}
    current_section = None
    current_lines = []
    for line in markdown_text.splitlines():
        if line.startswith("## "):
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = line.strip()
            current_lines = []
            continue
        if current_section is not None:
            current_lines.append(line)
    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()
    return sections


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
        require(
            parse_simple_yaml(scenario_path) == contract["required_metadata"],
            "scenario.yaml metadata does not match S06",
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
    section_bodies = extract_section_bodies(text)

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

    for section_requirement in contract.get("required_section_terms", []):
        section_name = section_requirement["section"]
        section_lower = section_bodies.get(section_name, "").lower()
        require(section_lower != "", f"Missing body for section: {section_name}", errors)
        for term in section_requirement["required_terms"]:
            require(
                term.lower() in section_lower,
                f"Missing required term '{term}' in section {section_name}",
                errors,
            )

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
