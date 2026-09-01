#!/usr/bin/env python3

# V3L02 verifier.
#
# History: this verifier previously returned a BINARY pass/fail even though its
# own contract (oracle/adr-long-horizon-contract.json score.max_points/pass_threshold
# and oracle/scoring-anchors.md) declares a graded 100-point / 85-threshold rubric.
# That gap (R4a) is fixed here: the completed-candidate path now computes the six
# declared scoring components, awards partial credit per component, applies the
# forbidden-claim integrity gate, and passes only when total >= pass_threshold.
# The bundle-shape gate and every structural check are preserved as a hard floor;
# grading only runs once the shape floor holds.

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the V3L02 bundle shape or score a completed ADR decision package."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root)
    parser.add_argument(
        "--candidate-root",
        type=Path,
        default=None,
        help="Optional alternate candidate directory (holds adr-decision.json + .md).",
    )
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument(
        "--json-report",
        action="store_true",
        help="Emit the scored component breakdown as JSON on stdout.",
    )
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


def term_fraction(value, terms):
    """Fraction (0..1) of required terms present in the serialized value."""
    if not terms:
        return 1.0
    text = normalize_text(value)
    hits = sum(1 for term in terms if term.lower() in text)
    return hits / len(terms)


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


# ----- graded component scorers -------------------------------------------------

def score_decision(data, contract):
    # 15 points: choice (8) + status (7).
    decision = data.get("decision", {}) if isinstance(data.get("decision"), dict) else {}
    pts = 0.0
    notes = []
    if decision.get("choice") == contract["decision"]["choice"]:
        pts += 8.0
    else:
        notes.append("decision.choice wrong")
    if decision.get("status") == contract["decision"]["status"]:
        pts += 7.0
    else:
        notes.append("decision.status wrong")
    return pts, 15.0, notes


def score_source_authority(data, contract):
    # 15 points: exact ordering full credit; correct set / wrong order = partial;
    # the tie-probe here is ranking the stale ADR LAST, so a wrong order (esp. stale
    # ADR ranked high) must lose most of the credit.
    expected = contract["source_authority_order"]
    actual = data.get("source_authority_order", [])
    if actual == expected:
        return 15.0, 15.0, []
    if isinstance(actual, list) and sorted(actual) == sorted(expected):
        return 6.0, 15.0, ["source_authority_order: right set, wrong ranking"]
    return 0.0, 15.0, ["source_authority_order mismatch"]


def score_id_terms_sources(data, key, expected_items, id_field, terms_field, per_item, errors_label):
    # Generic scorer for accepted_claims / rejected_options: each item worth
    # per_item points = present(0.4) + terms(0.3) + sources exact(0.3), scaled.
    actual_by_id = ids_by_key(data.get(key, []), id_field)
    total = per_item * len(expected_items)
    got = 0.0
    notes = []
    present_w, terms_w, src_w = 0.4, 0.3, 0.3
    for expected in expected_items:
        item_id = expected[id_field]
        actual = actual_by_id.get(item_id)
        if actual is None:
            notes.append(f"{errors_label} missing: {item_id}")
            continue
        got += per_item * present_w
        got += per_item * terms_w * term_fraction(actual, expected[terms_field])
        if sorted(actual.get("source_ids", [])) == sorted(expected["required_sources"]):
            got += per_item * src_w
        else:
            notes.append(f"{errors_label} {item_id} source_ids wrong")
    return got, total, notes


def score_compat_rollback(data, contract):
    # 20 points: compatibility_plan (4 items x 3 = 12) + rollback_plan (2 items x 4 = 8).
    got = 0.0
    notes = []
    compat_by_id = ids_by_key(data.get("compatibility_plan", []), "id")
    for expected in contract["compatibility_plan"]:
        actual = compat_by_id.get(expected["id"])
        if actual is None:
            notes.append(f"compatibility_plan missing: {expected['id']}")
            continue
        got += 1.0  # present
        got += 2.0 * term_fraction(actual, expected["required_terms"])
    rollback_by_id = ids_by_key(data.get("rollback_plan", []), "id")
    for expected in contract["rollback_plan"]:
        actual = rollback_by_id.get(expected["id"])
        if actual is None:
            notes.append(f"rollback_plan missing: {expected['id']}")
            continue
        got += 1.5  # present
        got += 2.5 * term_fraction(actual, expected["required_terms"])
    return got, 20.0, notes


def score_nonclaim_markdown(data, contract, md_path):
    # 10 points: non_claims (3 x 2 = 6) + markdown summary (4).
    got = 0.0
    notes = []
    nc_by_id = ids_by_key(data.get("non_claims", []), "id")
    for expected in contract["non_claims"]:
        actual = nc_by_id.get(expected["id"])
        if actual is None:
            notes.append(f"non_claims missing: {expected['id']}")
            continue
        got += 1.0  # present
        got += 1.0 * term_fraction(actual, expected["required_terms"])
    # markdown summary: 2 for all required sections present, 2 for gate_decision correct.
    if md_path.exists():
        md_text = md_path.read_text(encoding="utf-8")
        sections_present = sum(1 for s in contract["markdown_required_sections"] if s in md_text)
        got += 2.0 * (sections_present / len(contract["markdown_required_sections"]))
    else:
        notes.append("markdown summary missing")
    if data.get("gate_decision") == contract["gate_decision"]:
        got += 2.0
    else:
        notes.append("gate_decision wrong")
    return got, 10.0, notes


def integrity_forbidden(data, contract, md_path):
    """Return list of forbidden-claim hits across JSON (excluding non_claims) and md."""
    hits = []
    claim_checked = dict(data)
    claim_checked.pop("non_claims", None)
    serialized = normalize_text(claim_checked)
    md_text = ""
    if md_path.exists():
        md_lines = [
            line
            for line in md_path.read_text(encoding="utf-8").splitlines()
            if "do not claim" not in line.lower() and "not claim" not in line.lower()
        ]
        md_text = "\n".join(md_lines).lower()
    for forbidden in contract["forbidden_claims"]:
        f = forbidden.lower()
        if f in serialized:
            hits.append(f"JSON forbidden claim: {forbidden}")
        if f in md_text:
            hits.append(f"markdown forbidden claim: {forbidden}")
    return hits


def score_completed_candidate(bundle_root, candidate_root, contract):
    """Return (report_dict, fatal_errors)."""
    fatal = []
    json_path = candidate_root / "adr-decision.json"
    md_path = candidate_root / "adr-decision.md"

    if not json_path.exists():
        fatal.append("Missing candidate/adr-decision.json")
        return None, fatal
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fatal.append(f"candidate/adr-decision.json is invalid JSON: {exc}")
        return None, fatal
    if data.get("scenario_id") != contract["scenario_id"]:
        fatal.append("scenario_id mismatch")
        return None, fatal

    components = {}
    total = 0.0
    max_total = 0.0
    all_notes = []
    for name, (pts, mx, notes) in {
        "decision_choice": score_decision(data, contract),
        "source_authority": score_source_authority(data, contract),
        "accepted_claims": score_id_terms_sources(
            data, "accepted_claims", contract["accepted_claims"], "id",
            "summary_terms", 5.0, "accepted claim"),
        "rejected_options": score_id_terms_sources(
            data, "rejected_options", contract["rejected_options"], "option",
            "reason_terms", 5.0, "rejected option"),
        "compatibility_rollback": score_compat_rollback(data, contract),
        "nonclaim_markdown": score_nonclaim_markdown(data, contract, md_path),
    }.items():
        components[name] = {"points": round(pts, 2), "max": mx}
        total += pts
        max_total += mx
        all_notes.extend(notes)

    forbidden_hits = integrity_forbidden(data, contract, md_path)

    report = {
        "scenario_id": contract["scenario_id"],
        "components": components,
        "score": round(total, 2),
        "max_points": contract["score"]["max_points"],
        "pass_threshold": contract["score"]["pass_threshold"],
        "integrity_violations": forbidden_hits,
        "notes": all_notes,
    }
    return report, fatal


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
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        print("V3L02 verifier PASS (bundle shape)")
        return 0

    report, fatal = score_completed_candidate(bundle_root, candidate_root, contract)
    if fatal:
        for f in fatal:
            print(f"ERROR: {f}", file=sys.stderr)
        return 1

    threshold = report["pass_threshold"]
    passed = report["score"] >= threshold and not report["integrity_violations"]

    if args.json_report:
        print(json.dumps(report, indent=2))
    else:
        for name, comp in report["components"].items():
            print(f"  {name}: {comp['points']}/{comp['max']}")
        if report["integrity_violations"]:
            for v in report["integrity_violations"]:
                print(f"  INTEGRITY: {v}", file=sys.stderr)
        for note in report["notes"]:
            print(f"  note: {note}", file=sys.stderr)

    verdict = "PASS" if passed else "FAIL"
    stream = sys.stdout if passed else sys.stderr
    print(
        f"V3L02 graded score {report['score']}/{report['max_points']} "
        f"(threshold {threshold}) -> {verdict}",
        file=stream,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
