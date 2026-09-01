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
    parser.add_argument(
        "--candidate-file",
        type=Path,
        default=None,
        help="Optional alternate advisory memo path (for reference/probe scoring).",
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


def contains_any(text, alternatives):
    lowered = text.lower()
    return any(option.lower() in lowered for option in alternatives)


# ----- R4b counterfactual-consequence graded scorer -----------------------------

def section_block(text, heading):
    """Body of a '## '-level section (heading -> next '## ' or EOF)."""
    start = text.find(heading)
    if start == -1:
        return ""
    body_start = start + len(heading)
    rest = text[body_start:]
    nxt = rest.find("\n## ")
    return rest if nxt == -1 else rest[:nxt]


def marker_block(text, start_marker, end_markers):
    start = text.find(start_marker)
    if start == -1:
        return ""
    body_start = start + len(start_marker)
    rest = text[body_start:]
    end = len(rest)
    for marker in end_markers:
        idx = rest.find(marker)
        if idx != -1:
            end = min(end, idx)
    return rest[:end]


def any_hit(text, options):
    low = text.lower()
    return any(opt.lower() in low for opt in options)


def score_counterfactual(text, spec):
    """Return (score, mandatory_ok, breakdown, notes)."""
    scopes = {
        "whole": text,
        "recommended_block": section_block(text, spec["recommended_block_heading"]),
        "uncertainty_block": section_block(text, spec["uncertainty_block_heading"]),
        "alternative_block": marker_block(
            text, spec["alternative_block_start"], spec["alternative_block_end_markers"]
        ),
    }
    breakdown = {}
    notes = []
    total = 0.0
    mandatory_ok = True

    for name, comp in spec["components"].items():
        scope_text = scopes.get(comp.get("scope", "whole"), text)
        pts = comp["points"]
        if "conjunction" in comp:
            groups = comp["conjunction"]
            hits = sum(1 for g in groups if any_hit(scope_text, g["any_of"]))
            earned = pts * (hits / len(groups))
            missing = [g["group"] for g in groups if not any_hit(scope_text, g["any_of"])]
            if missing:
                notes.append(f"{name}: missing groups {missing}")
        else:
            earned = pts if any_hit(scope_text, comp["any_of"]) else 0.0
            if earned == 0.0:
                notes.append(f"{name}: no evidence in scope '{comp.get('scope')}'")
        breakdown[name] = round(earned, 2)
        total += earned
        if "mandatory_min" in comp and earned < comp["mandatory_min"]:
            mandatory_ok = False
            notes.append(
                f"{name}: earned {round(earned, 2)} < mandatory_min {comp['mandatory_min']} "
                "(the counterfactual consequence is required, not optional)"
            )

    # decoy-driver diagnostic: a memo leaning on shallow drivers while the mandatory
    # consequence reasoning is absent is exactly the adversarial decoy this catches.
    decoy = spec.get("decoy_drivers")
    if decoy and any_hit(scopes.get(decoy["scope"], text), decoy["any_of"]) and not mandatory_ok:
        notes.append("decoy-driver: recommendation leans on shallow driver without the derived consequence")

    return round(total, 2), mandatory_ok, breakdown, notes


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


def check_completed_memo(bundle_root: Path, contract, errors, memo_path=None):
    if memo_path is None:
        memo_path = bundle_root / "candidate" / "advisory-memo.md"
    require(memo_path.exists(), f"Missing memo file: {memo_path}", errors)
    if errors:
        return

    text = memo_path.read_text(encoding="utf-8")
    section_bodies = extract_section_bodies(text)

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
    memo_path = args.candidate_file.resolve() if args.candidate_file else None
    if not args.bundle_shape_only:
        check_completed_memo(bundle_root, contract, errors, memo_path=memo_path)

    # Floor gate: structural + fixed-string + keyword checks are a hard prerequisite.
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        print("S03 verifier PASS (bundle shape)")
        return 0

    # R4b graded layer: counterfactual-consequence discrimination above the floor.
    spec = contract.get("counterfactual_scoring")
    if spec is None:
        print("S03 verifier PASS (completed consultant memo; no graded spec)")
        return 0

    resolved = memo_path if memo_path else bundle_root / "candidate" / "advisory-memo.md"
    text = resolved.read_text(encoding="utf-8")
    score, mandatory_ok, breakdown, notes = score_counterfactual(text, spec)
    threshold = spec["pass_threshold"]
    passed = score >= threshold and mandatory_ok

    for name, pts in breakdown.items():
        print(f"  {name}: {pts}")
    for note in notes:
        print(f"  note: {note}", file=sys.stderr)

    verdict = "PASS" if passed else "FAIL"
    stream = sys.stdout if passed else sys.stderr
    print(
        f"S03 counterfactual score {score}/{spec['max_points']} "
        f"(threshold {threshold}, mandatory_ok={mandatory_ok}) -> {verdict}",
        file=stream,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
