#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S08 UX bundle shape or a completed UX structure brief."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S08 bundle root.",
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
        help="Optional alternate ux-structure-brief path (for reference/probe scoring).",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "ux-brief-contract.json"
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


def check_ordered_headings(text: str, headings: list[str], label: str, errors: list[str]) -> None:
    last_index = -1
    for heading in headings:
        index = text.find(heading)
        require(index >= 0, f"Missing {label}: {heading}", errors)
        if index >= 0:
            require(index > last_index, f"{label} out of order: {heading}", errors)
            last_index = index


def check_bundle_shape(bundle_root: Path, contract, errors):
    expected_entries = contract["required_top_level_entries"]
    actual_entries = sorted(path.name for path in bundle_root.iterdir())
    require(
        actual_entries == sorted(expected_entries),
        "Bundle root top-level entries do not match the required six-entry contract exactly",
        errors,
    )

    for entry in expected_entries:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

    candidate_root = bundle_root / "candidate"
    if candidate_root.exists():
        actual_candidate_entries = sorted(path.name for path in candidate_root.iterdir())
        require(
            actual_candidate_entries == sorted(contract["expected_candidate_entries"]),
            "candidate/ contains files beyond the single UX brief contract",
            errors,
        )

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


def check_completed_brief(bundle_root: Path, contract, errors, brief_path=None):
    if brief_path is None:
        brief_path = bundle_root / "candidate" / "ux-structure-brief.md"
    require(brief_path.exists(), f"Missing ux-structure-brief file: {brief_path}", errors)
    if errors:
        return

    text = brief_path.read_text(encoding="utf-8")
    section_bodies = extract_section_bodies(text)

    for section in contract["required_brief_sections"]:
        require(section in text, f"Missing required section: {section}", errors)

    check_ordered_headings(text, contract["required_surface_headings"], "surface heading", errors)
    check_ordered_headings(text, contract["required_flow_headings"], "flow heading", errors)
    check_ordered_headings(text, contract["required_state_headings"], "state heading", errors)

    for exact_line in contract["required_exact_lines"]:
        require(exact_line in text, f"Missing required line: {exact_line}", errors)

    for alternatives in contract["required_keyword_groups"]:
        require(
            contains_any(text, alternatives),
            f"Brief is missing required keyword coverage from: {alternatives}",
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

    status_pattern = r"(?ms)^## Brief status\s+([A-Z][A-Z -]+)\s*\Z"
    match = re.search(status_pattern, text)
    require(match is not None, "Brief status section is missing or malformed", errors)
    if match is not None:
        require(
            match.group(1) in contract["valid_statuses"],
            "Brief status is not an allowed value",
            errors,
        )

    for marker in contract["disallowed_markers"]:
        require(marker not in text, f"Disallowed marker present in brief: {marker}", errors)


# ----- R4b derivation (priority/sequence ordering) graded scorer ----------------

def _any_hit(text, options):
    low = text.lower()
    return any(opt.lower() in low for opt in options)


def _section_body(text, heading):
    start = text.find(heading)
    if start == -1:
        return ""
    rest = text[start + len(heading):]
    nxt = rest.find("\n## ")
    return rest if nxt == -1 else rest[:nxt]


def _build_scopes(text, spec):
    scopes = {"whole": text}
    for name, headings in spec.get("scopes", {}).items():
        scopes[name] = "\n".join(_section_body(text, h) for h in headings)
    return scopes


def _first_index(text, terms):
    low = text.lower()
    idxs = [low.find(t.lower()) for t in terms if low.find(t.lower()) != -1]
    return min(idxs) if idxs else -1


def _eval_lead(scope_text, comp):
    low = _first_index(scope_text, comp["low"])
    high = _first_index(scope_text, comp["high"])
    if high == -1:
        return 0.0, "lead: no high-priority anchor present in scope"
    if low == -1 or high < low:
        return float(comp["points"]), ""
    return 0.0, "lead: a lower-priority element leads the ladder (inverted ranking)"


def _eval_order_pairs(scope_text, comp):
    pairs = comp["pairs"]
    per = comp["points"] / len(pairs)
    earned = 0.0
    bad = []
    low = scope_text.lower()
    for a, b in pairs:
        ia = low.find(a.lower())
        ib = low.find(b.lower())
        if ia != -1 and ib != -1 and ia < ib:
            earned += per
        else:
            bad.append(f"{a}<{b}")
    return earned, (f"order_pairs violated/missing: {bad}" if bad else "")


def _eval_conjunction(scope_text, comp):
    groups = comp["conjunction"]
    hits = sum(1 for g in groups if _any_hit(scope_text, g["any_of"]))
    earned = comp["points"] * (hits / len(groups))
    missing = [g["group"] for g in groups if not _any_hit(scope_text, g["any_of"])]
    return earned, (f"conjunction missing groups {missing}" if missing else "")


def score_ordering(text, spec):
    scopes = _build_scopes(text, spec)
    breakdown = {}
    notes = []
    total = 0.0
    mandatory_ok = True
    for name, comp in spec["components"].items():
        scope_text = scopes.get(comp.get("scope", "whole"), text)
        ctype = comp["type"]
        if ctype == "lead":
            earned, msg = _eval_lead(scope_text, comp)
        elif ctype == "order_pairs":
            earned, msg = _eval_order_pairs(scope_text, comp)
        elif ctype == "conjunction":
            earned, msg = _eval_conjunction(scope_text, comp)
        elif ctype == "any_of":
            earned = float(comp["points"]) if _any_hit(scope_text, comp["any_of"]) else 0.0
            msg = "" if earned else f"any_of: no evidence in scope '{comp.get('scope')}'"
        else:
            earned, msg = 0.0, f"unknown component type {ctype}"
        breakdown[name] = round(earned, 2)
        total += earned
        if msg:
            notes.append(f"{name}: {msg}")
        if comp.get("mandatory") and earned < comp.get("mandatory_min", comp["points"]):
            mandatory_ok = False
            notes.append(f"{name}: below mandatory_min (the derived ordering/gating is required)")
    return round(total, 2), mandatory_ok, breakdown, notes


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    errors = []

    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    contract = load_contract(bundle_root)
    check_bundle_shape(bundle_root, contract, errors)
    brief_path = args.candidate_file.resolve() if args.candidate_file else None
    if not args.bundle_shape_only:
        check_completed_brief(bundle_root, contract, errors, brief_path=brief_path)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        print("S08 verifier PASS (bundle shape)")
        return 0

    spec = contract.get("ordering_scoring")
    if spec is None:
        print("S08 verifier PASS (completed brief; no graded spec)")
        return 0

    resolved = brief_path if brief_path else bundle_root / "candidate" / "ux-structure-brief.md"
    text = resolved.read_text(encoding="utf-8")
    score, mandatory_ok, breakdown, notes = score_ordering(text, spec)
    threshold = spec["pass_threshold"]
    passed = score >= threshold and mandatory_ok
    for name, pts in breakdown.items():
        print(f"  {name}: {pts}")
    for note in notes:
        print(f"  note: {note}", file=sys.stderr)
    verdict = "PASS" if passed else "FAIL"
    stream = sys.stdout if passed else sys.stderr
    print(f"S08 ordering score {score}/{spec['max_points']} "
          f"(threshold {threshold}, mandatory_ok={mandatory_ok}) -> {verdict}", file=stream)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
