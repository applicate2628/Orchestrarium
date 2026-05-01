#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the V3L02 bundle shape or completed ADR decision package."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root)
    parser.add_argument(
        "--candidate-root",
        type=Path,
        default=None,
        help="Optional alternate candidate directory for reference probes.",
    )
    parser.add_argument("--bundle-shape-only", action="store_true")
    return parser.parse_args()


def strip_quotes(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_yaml(path):
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


def top_level_yaml_keys(path):
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


def normalize_text(value):
    if isinstance(value, str):
        return value.lower()
    return json.dumps(value, sort_keys=True).lower()


def contains_terms(value, terms):
    text = normalize_text(value)
    return all(term.lower() in text for term in terms)


def ids_by_key(items, key):
    result = {}
    for item in items:
        if isinstance(item, dict) and key in item:
            result[item[key]] = item
    return result


def load_contract(bundle_root):
    return json.loads(
        (bundle_root / "oracle" / "adr-long-horizon-contract.json").read_text(
            encoding="utf-8"
        )
    )


def check_bundle_shape(bundle_root, contract, errors):
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
    if scenario_path.exists():
        require(
            top_level_yaml_keys(scenario_path) == contract["scenario_yaml_fields"],
            "scenario.yaml fields do not match the required contract order exactly",
            errors,
        )
        require(
            parse_simple_yaml(scenario_path) == contract["required_metadata"],
            "scenario.yaml metadata does not match V3L02",
            errors,
        )


def check_markdown(markdown_path, contract, errors):
    require(markdown_path.exists(), "Missing candidate/adr-decision.md", errors)
    if not markdown_path.exists():
        return
    text = markdown_path.read_text(encoding="utf-8")
    for section in contract["markdown_required_sections"]:
        require(section in text, f"Markdown missing section: {section}", errors)
    claim_lines = [
        line
        for line in text.splitlines()
        if "do not claim" not in line.lower() and "not claim" not in line.lower()
    ]
    claim_text = "\n".join(claim_lines).lower()
    for forbidden in contract["forbidden_claims"]:
        require(
            forbidden.lower() not in claim_text,
            f"Markdown contains forbidden claim: {forbidden}",
            errors,
        )


def check_completed_candidate(bundle_root, candidate_root, contract, errors):
    json_path = candidate_root / "adr-decision.json"
    md_path = candidate_root / "adr-decision.md"

    require(json_path.exists(), "Missing candidate/adr-decision.json", errors)
    if not json_path.exists():
        return

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"candidate/adr-decision.json is invalid JSON: {exc}")
        return

    require(data.get("scenario_id") == contract["scenario_id"], "scenario_id mismatch", errors)

    decision = data.get("decision", {})
    require(
        decision.get("choice") == contract["decision"]["choice"],
        "decision.choice mismatch",
        errors,
    )
    require(
        decision.get("status") == contract["decision"]["status"],
        "decision.status mismatch",
        errors,
    )

    require(
        data.get("source_authority_order") == contract["source_authority_order"],
        "source_authority_order mismatch",
        errors,
    )

    claims = ids_by_key(data.get("accepted_claims", []), "id")
    for expected in contract["accepted_claims"]:
        actual = claims.get(expected["id"])
        require(actual is not None, f"Missing accepted claim: {expected['id']}", errors)
        if actual is None:
            continue
        require(
            contains_terms(actual, expected["summary_terms"]),
            f"Accepted claim {expected['id']} missing required terms",
            errors,
        )
        require(
            sorted(actual.get("source_ids", [])) == sorted(expected["required_sources"]),
            f"Accepted claim {expected['id']} source_ids mismatch",
            errors,
        )

    rejected = ids_by_key(data.get("rejected_options", []), "option")
    for expected in contract["rejected_options"]:
        actual = rejected.get(expected["option"])
        require(actual is not None, f"Missing rejected option: {expected['option']}", errors)
        if actual is None:
            continue
        require(
            contains_terms(actual, expected["reason_terms"]),
            f"Rejected option {expected['option']} missing required terms",
            errors,
        )
        require(
            sorted(actual.get("source_ids", [])) == sorted(expected["required_sources"]),
            f"Rejected option {expected['option']} source_ids mismatch",
            errors,
        )

    for section_name in ["compatibility_plan", "rollback_plan", "non_claims"]:
        actual_by_id = ids_by_key(data.get(section_name, []), "id")
        for expected in contract[section_name]:
            actual = actual_by_id.get(expected["id"])
            require(actual is not None, f"Missing {section_name} item: {expected['id']}", errors)
            if actual is None:
                continue
            require(
                contains_terms(actual, expected["required_terms"]),
                f"{section_name} item {expected['id']} missing required terms",
                errors,
            )

    require(
        data.get("gate_decision") == contract["gate_decision"],
        "gate_decision mismatch",
        errors,
    )

    claim_checked_data = dict(data)
    claim_checked_data.pop("non_claims", None)
    serialized = normalize_text(claim_checked_data)
    for forbidden in contract["forbidden_claims"]:
        require(
            forbidden.lower() not in serialized,
            f"JSON contains forbidden claim: {forbidden}",
            errors,
        )

    check_markdown(md_path, contract, errors)


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    candidate_root = (
        args.candidate_root.resolve() if args.candidate_root else bundle_root / "candidate"
    )
    errors = []

    require(bundle_root.exists(), f"Bundle root does not exist: {bundle_root}", errors)
    if errors:
        print(errors[0], file=sys.stderr)
        return 1

    contract = load_contract(bundle_root)
    check_bundle_shape(bundle_root, contract, errors)
    if not args.bundle_shape_only:
        check_completed_candidate(bundle_root, candidate_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed ADR decision"
    print(f"V3L02 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
