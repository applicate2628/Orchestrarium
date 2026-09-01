#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check N98 visual regression diff answer.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--answer-file", type=Path)
    parser.add_argument("--metrics-out", type=Path)
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def contains_any(text: str, terms: list[str]) -> bool:
    return any(term.lower() in text for term in terms)


def extract_json(raw: str):
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        pass

    first = text.find("{")
    if first >= 0:
        depth = 0
        in_string = False
        escape = False
        for index in range(first, len(text)):
            char = text[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[first : index + 1]
                    try:
                        return json.loads(candidate), None
                    except json.JSONDecodeError as exc:
                        return None, str(exc)
    return None, "no JSON object found"


def parse_simple_yaml(path: Path):
    data = {}
    current_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            data.setdefault(current_key, []).append(line[4:].strip().strip('"'))
            continue
        if ":" not in line or line.startswith(" "):
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value == "":
            data[key] = []
            current_key = key
        else:
            data[key] = value.strip('"')
            current_key = None
    return data


def check_shape(root: Path, contract: dict, errors: list[str]):
    entries = sorted(path.name for path in root.iterdir())
    if entries != sorted(contract["required_top_level_entries"]):
        errors.append(f"top-level entries drifted: {entries}")
    if parse_simple_yaml(root / "scenario.yaml").get("id") != "N98":
        errors.append("scenario id mismatch")
    for relative in contract["required_bundle_paths"]:
        if not (root / relative).exists():
            errors.append(f"missing required path: {relative}")


def check_changed_paths(changed_paths: list[str], contract: dict, errors: list[str]):
    if not changed_paths:
        return
    expected = sorted(contract["requiredChangedPaths"])
    actual = sorted(changed_paths)
    if actual != expected:
        errors.append(f"changed paths mismatch: expected {expected}, got {actual}")


def distance_px(finding: dict, expected: dict) -> float:
    try:
        x = float(finding.get("x"))
        y = float(finding.get("y"))
    except (TypeError, ValueError):
        return math.inf
    target = expected["target"]
    return math.hypot(x - target["x"], y - target["y"])


def finding_text(finding: dict) -> str:
    return " ".join(
        [
            normalize(finding.get("component")),
            normalize(finding.get("defect")),
            normalize(finding.get("evidence")),
        ]
    )


def score_answer(answer: dict | None, parse_error: str | None, contract: dict):
    expected = {item["id"]: item for item in contract["expectedFindings"]}
    tolerance = float(contract["coordinate_tolerance_px"])
    metrics = {
        "verdict": "FAIL",
        "score_0_100": 0.0,
        "matched_count": 0,
        "expected_count": len(expected),
        "pass_min_matched": int(contract["pass_min_matched"]),
        "pass_score_threshold_0_100": float(contract["pass_score_threshold_0_100"]),
        "false_positive_count": 0,
        "parse_error": parse_error,
        "failures": [],
        "warnings": [],
        "matches": [],
        "unmatched_expected": [],
        "unmatched_findings": [],
        "false_positive_hits": [],
        "non_finding_coverage_count": 0,
        "non_finding_expected_count": len(contract["requiredNonFindings"]),
        "missing_non_findings": [],
        "mean_error_px": None,
        "max_error_px": None,
    }
    if answer is None:
        metrics["failures"].append(parse_error or "answer parse failed")
        return metrics
    if answer.get("image_id") != contract["image_id"]:
        metrics["failures"].append("image_id mismatch")
    findings = answer.get("findings")
    if not isinstance(findings, list):
        metrics["failures"].append("findings must be a list")
        findings = []
    if len(findings) != len(expected):
        metrics["failures"].append(f"expected {len(expected)} findings, got {len(findings)}")

    seen_ids: set[str] = set()
    usable_findings: list[dict] = []
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            metrics["failures"].append(f"finding {index} is not an object")
            continue
        finding_id = str(finding.get("id", ""))
        if finding_id in seen_ids:
            metrics["failures"].append(f"duplicate finding id: {finding_id}")
            continue
        seen_ids.add(finding_id)
        usable_findings.append(finding)
        text = finding_text(finding)
        for trap in contract["falsePositiveTerms"]:
            if all(term.lower() in text for term in trap):
                metrics["false_positive_hits"].append({"id": finding_id, "terms": trap})

    expected_ids = set(expected)
    allowed_ids = expected_ids
    unknown_ids = sorted(seen_ids - allowed_ids)
    if unknown_ids:
        metrics["failures"].append("unknown finding id(s): " + ", ".join(unknown_ids))

    candidates: list[tuple[int, float, str, int, dict]] = []
    for index, finding in enumerate(usable_findings):
        text = finding_text(finding)
        for expected_id, exp in expected.items():
            dist = distance_px(finding, exp)
            component_ok = contains_any(text, exp["component_terms"])
            defect_ok = contains_any(text, exp["defect_terms"])
            finding_tolerance = float(exp.get("tolerance_px", tolerance))
            coordinate_ok = dist <= finding_tolerance
            if component_ok and defect_ok and coordinate_ok:
                severity_ok = finding.get("severity") == exp["severity"]
                quality = (1 if severity_ok else 0)
                candidates.append((quality, dist, expected_id, index, finding))

    matched_expected: set[str] = set()
    matched_indices: set[int] = set()
    distances: list[float] = []
    severity_mismatches = 0
    for quality, dist, expected_id, index, finding in sorted(candidates, key=lambda item: (-item[0], item[1])):
        if expected_id in matched_expected or index in matched_indices:
            continue
        matched_expected.add(expected_id)
        matched_indices.add(index)
        if quality == 0:
            severity_mismatches += 1
        metrics["matches"].append(
            {
                "expected_id": expected_id,
                "reported_id": finding.get("id"),
                "distance_px": round(dist, 3),
                "severity_ok": quality == 1,
            }
        )
        distances.append(dist)

    metrics["unmatched_expected"] = sorted(expected_ids - matched_expected)
    for index, finding in enumerate(usable_findings):
        if index not in matched_indices:
            metrics["unmatched_findings"].append(
                {
                    "reported_id": finding.get("id"),
                    "component": finding.get("component"),
                    "defect": finding.get("defect"),
                    "x": finding.get("x"),
                    "y": finding.get("y"),
                }
            )
    metrics["matched_count"] = len(metrics["matches"])
    metrics["false_positive_count"] = len(metrics["false_positive_hits"]) + len(metrics["unmatched_findings"])
    if metrics["unmatched_findings"]:
        metrics["failures"].append(f"unmatched findings: {len(metrics['unmatched_findings'])}")
    if severity_mismatches:
        metrics["warnings"].append(f"severity mismatches among matched findings: {severity_mismatches}")
    if distances:
        metrics["mean_error_px"] = round(sum(distances) / len(distances), 3)
        metrics["max_error_px"] = round(max(distances), 3)

    non_findings = [normalize(item) for item in answer.get("non_findings", []) if isinstance(item, str)]
    for required in contract["requiredNonFindings"]:
        required_tokens = [part for part in re.split(r"[/\s]+", required.lower()) if part]
        if any(all(token in item for token in required_tokens) for item in non_findings):
            metrics["non_finding_coverage_count"] += 1
        else:
            metrics["missing_non_findings"].append(required)
    if metrics["missing_non_findings"]:
        metrics["warnings"].append("missing non-findings: " + ", ".join(metrics["missing_non_findings"]))

    base_score = (metrics["matched_count"] / len(expected)) * 90.0
    non_finding_score = (metrics["non_finding_coverage_count"] / len(contract["requiredNonFindings"])) * 10.0
    penalty = metrics["false_positive_count"] * 10.0 + severity_mismatches * 1.0
    metrics["score_0_100"] = round(max(0.0, base_score + non_finding_score - penalty), 1)
    if (
        metrics["matched_count"] >= metrics["pass_min_matched"]
        and metrics["score_0_100"] >= metrics["pass_score_threshold_0_100"]
        and metrics["false_positive_count"] < 2
        and not [f for f in metrics["failures"] if f.startswith("expected") or f.startswith("image_id") or f.startswith("unknown")]
    ):
        metrics["verdict"] = "PASS"
    return metrics


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "visual-regression-contract.json")
    errors: list[str] = []
    check_shape(root, contract, errors)
    check_changed_paths(args.changed_paths, contract, errors)

    if args.bundle_shape_only:
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("N98 verifier PASS (bundle shape)")
        return 0

    answer_path = args.answer_file or (root / "candidate" / "answer.json")
    raw = answer_path.read_text(encoding="utf-8") if answer_path.exists() else ""
    answer, parse_error = extract_json(raw)
    metrics = score_answer(answer, parse_error, contract)
    metrics["failures"] = errors + metrics["failures"]

    if args.metrics_out:
        args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    if args.expect_start_state:
        if metrics["verdict"] != "PASS" or metrics["failures"]:
            print("N98 verifier PASS (expected start-state failures present)")
            return 0
        print("ERROR: start state unexpectedly passes", file=sys.stderr)
        return 1

    if metrics["verdict"] != "PASS" or metrics["failures"]:
        for failure in metrics["failures"]:
            print(f"ERROR: {failure}", file=sys.stderr)
        print(json.dumps(metrics, indent=2), file=sys.stderr)
        return 1

    print(f"N98 verifier PASS ({metrics['score_0_100']} / 100)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
