#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N84 security repro-review bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    parser.add_argument("--expect-start-state", action="store_true")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def strip_quotes(value: str) -> str:
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
            data.setdefault(current_key, []).append(strip_quotes(line[4:].strip()))
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
            data[key] = strip_quotes(value)
            current_key = None
    return data


def top_level_yaml_keys(path: Path):
    keys = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line and not line.startswith(" ") and not line.startswith("#") and ":" in line:
            keys.append(line.split(":", 1)[0].strip())
    return keys


def require(condition: bool, message: str, errors: list[str]):
    if not condition:
        errors.append(message)


def text_has_all(value, terms):
    text = str(value or "").lower()
    return all(str(term).lower() in text for term in terms)


def text_has_any(value, terms):
    text = str(value or "").lower()
    return any(str(term).lower() in text for term in terms)


def check_shape(root: Path, contract: dict, errors: list[str]):
    actual_entries = sorted(path.name for path in root.iterdir())
    require(
        actual_entries == sorted(contract["required_top_level_entries"]),
        f"Top-level bundle entries drifted: {actual_entries}",
        errors,
    )
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", errors)
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", errors)
    for relative_path in contract["required_bundle_paths"]:
        require((root / relative_path).exists(), f"Missing required bundle path: {relative_path}", errors)


def check_changed_paths(changed_paths: list[str], contract: dict, errors: list[str]):
    allowed = set(contract["expected_metadata"]["allowed_change_surface"])
    unexpected = sorted(path for path in changed_paths if path not in allowed)
    if unexpected:
        errors.append("Changed path outside allowed surface: " + ", ".join(unexpected))


def check_finding(candidate: dict, oracle: dict, errors: list[str]):
    prefix = oracle["id"]
    require(candidate.get("id") == oracle["id"], f"{prefix}: id mismatch", errors)
    require(candidate.get("file") == oracle["file"], f"{prefix}: file mismatch", errors)
    require(candidate.get("line") in oracle["acceptable_lines"], f"{prefix}: line mismatch", errors)
    require(candidate.get("category") == oracle["category"], f"{prefix}: category mismatch", errors)
    require(candidate.get("severity") == oracle["severity"], f"{prefix}: severity mismatch", errors)
    require(text_has_any(candidate.get("title"), oracle["title_keywords"]), f"{prefix}: title missing anchor", errors)
    require(text_has_all(candidate.get("sourceEvidence"), oracle["source_terms"]), f"{prefix}: sourceEvidence missing terms", errors)

    reproduction = candidate.get("reproduction")
    require(isinstance(reproduction, dict), f"{prefix}: reproduction must be an object", errors)
    if not isinstance(reproduction, dict):
        return
    expected_repro = oracle["repro"]
    require(reproduction.get("caseId") == expected_repro["caseId"], f"{prefix}: reproduction.caseId mismatch", errors)
    require(text_has_all(reproduction.get("attackerAction"), expected_repro["attacker_terms"]), f"{prefix}: attackerAction missing terms", errors)
    require(text_has_all(reproduction.get("observedImpact"), expected_repro["impact_terms"]), f"{prefix}: observedImpact missing terms", errors)
    require(text_has_all(reproduction.get("violatedInvariant"), expected_repro["invariant_terms"]), f"{prefix}: violatedInvariant missing terms", errors)
    require(text_has_all(candidate.get("fixBoundary"), oracle["fix_terms"]), f"{prefix}: fixBoundary missing terms", errors)


def check_false_positives(report: dict, contract: dict, errors: list[str]):
    items = report.get("falsePositiveAvoided")
    require(isinstance(items, list), "falsePositiveAvoided must be a list", errors)
    if not isinstance(items, list):
        return
    by_case = {item.get("caseId"): item for item in items if isinstance(item, dict)}
    require(len(by_case) == len(items), "falsePositiveAvoided case ids must be distinct", errors)
    for expected in contract["required_false_positive_cases"]:
        item = by_case.get(expected["caseId"])
        require(item is not None, f"missing false-positive case {expected['caseId']}", errors)
        if not item:
            continue
        require(text_has_all(item.get("pattern"), expected["pattern_terms"]), f"{expected['caseId']}: pattern missing terms", errors)
        require(text_has_all(item.get("reason"), expected["reason_terms"]), f"{expected['caseId']}: reason missing terms", errors)


def check_report(root: Path, contract: dict, errors: list[str]):
    report_path = root / contract["editable_report"]
    require(report_path.exists(), f"Missing candidate report: {contract['editable_report']}", errors)
    if not report_path.exists():
        return
    try:
        report = load_json(report_path)
    except Exception as exc:  # noqa: BLE001 - verifier reports candidate artifact
        errors.append(f"Report is not valid JSON: {exc}")
        return

    require(
        sorted(report.keys()) == sorted(contract["required_top_level_report_keys"]),
        f"Report top-level keys mismatch: {sorted(report.keys())}",
        errors,
    )
    require(report.get("contractId") == contract["contractId"], "contractId mismatch", errors)
    require(report.get("gateDecision") == contract["expected_gate_decision"], "gateDecision mismatch", errors)
    raw_report = json.dumps(report, sort_keys=True)
    for snippet in contract["prohibited_report_snippets"]:
        require(snippet.lower() not in raw_report.lower(), f"Prohibited snippet present: {snippet}", errors)

    findings = report.get("findings")
    require(isinstance(findings, list), "findings must be a list", errors)
    if not isinstance(findings, list):
        return
    require(len(findings) == contract["exact_finding_count"], f"expected {contract['exact_finding_count']} findings, got {len(findings)}", errors)

    allowed_categories = set(contract["allowed_categories"])
    allowed_severities = set(contract["allowed_severities"])
    by_id = {}
    for index, finding in enumerate(findings, start=1):
        require(isinstance(finding, dict), f"finding {index} must be an object", errors)
        if not isinstance(finding, dict):
            continue
        fid = finding.get("id")
        require(fid not in by_id, f"duplicate finding id: {fid}", errors)
        by_id[fid] = finding
        require(finding.get("category") in allowed_categories, f"{fid}: invalid category", errors)
        require(finding.get("severity") in allowed_severities, f"{fid}: invalid severity", errors)
        repro = finding.get("reproduction")
        if isinstance(repro, dict):
            require(not str(repro.get("caseId", "")).startswith("B"), f"{fid}: benign probe used as finding", errors)

    for oracle in contract["required_findings"]:
        candidate = by_id.get(oracle["id"])
        require(candidate is not None, f"missing required finding {oracle['id']}", errors)
        if candidate is not None:
            check_finding(candidate, oracle, errors)

    check_false_positives(report, contract, errors)


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "security-repro-review-contract.json")
    errors: list[str] = []
    check_shape(root, contract, errors)
    if args.changed_paths:
        check_changed_paths(args.changed_paths, contract, errors)
    if args.bundle_shape_only:
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("N84 verifier PASS (bundle shape)")
        return 0

    check_report(root, contract, errors)
    if args.expect_start_state:
        expected = {"expected 9 findings", "gateDecision mismatch"}
        observed = "\n".join(errors)
        missing = [needle for needle in expected if needle not in observed]
        if missing:
            print(f"ERROR: start state no longer exposes expected failures: {missing}", file=sys.stderr)
            return 1
        print("N84 verifier PASS (expected start-state failures present)")
        return 0

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("N84 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
