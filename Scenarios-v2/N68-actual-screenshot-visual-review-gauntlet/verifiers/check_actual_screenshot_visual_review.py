#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N68 actual screenshot visual review bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--answer-file", type=Path)
    parser.add_argument("--metrics-out", type=Path)
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
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


def require(condition: bool, message: str, errors: list[str]):
    if not condition:
        errors.append(message)


def normalize(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower())


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


def check_shape(root: Path, contract: dict, errors: list[str]):
    actual_entries = sorted(path.name for path in root.iterdir())
    require(
        actual_entries == sorted(contract["required_top_level_entries"]),
        f"Top-level bundle entries drifted: {actual_entries}",
        errors,
    )
    metadata = parse_simple_yaml(root / "scenario.yaml")
    require(metadata.get("id") == "N68", "scenario id mismatch", errors)
    for path in contract["required_bundle_paths"]:
        require((root / path).exists(), f"Missing required bundle path: {path}", errors)


def check_changed_paths(changed_paths: list[str], contract: dict, errors: list[str]):
    if not changed_paths:
        return
    expected = sorted(contract["requiredChangedPaths"])
    actual = sorted(changed_paths)
    require(actual == expected, f"changed paths mismatch: expected {expected}, got {actual}", errors)


def distance_px(finding: dict, expected: dict):
    try:
        x = float(finding.get("x"))
        y = float(finding.get("y"))
    except (TypeError, ValueError):
        return math.inf
    target = expected["target"]
    return math.hypot(x - target["x"], y - target["y"])


def score_answer(answer: dict | None, parse_error: str | None, contract: dict):
    metrics = {
        "verdict": "FAIL",
        "score_0_100": 0.0,
        "matched_count": 0,
        "expected_count": len(contract["expectedFindings"]),
        "false_positive_count": 0,
        "parse_error": parse_error,
        "failures": [],
        "matches": [],
    }
    if answer is None:
        metrics["failures"].append("parse-error")
        return metrics

    if answer.get("image_id") != contract["image_id"]:
        metrics["failures"].append("image-id")

    findings = answer.get("findings")
    if not isinstance(findings, list):
        metrics["failures"].append("findings-not-list")
        findings = []
    if len(findings) != len(contract["expectedFindings"]):
        metrics["failures"].append(f"finding-count-{len(findings)}")

    used_indices: set[int] = set()
    tolerance = float(contract["coordinate_tolerance_px"])
    for expected in contract["expectedFindings"]:
        best = None
        for index, finding in enumerate(findings):
            if index in used_indices or not isinstance(finding, dict):
                continue
            text = " ".join(
                [
                    normalize(finding.get("component")),
                    normalize(finding.get("defect")),
                    normalize(finding.get("evidence")),
                ]
            )
            component_ok = contains_any(text, expected["component_terms"])
            defect_ok = contains_any(text, expected["defect_terms"])
            dist = distance_px(finding, expected)
            if component_ok and defect_ok and dist <= tolerance:
                best = (index, dist, finding)
                break
        if best is None:
            metrics["failures"].append(f"miss-{expected['id']}")
            continue
        used_indices.add(best[0])
        metrics["matched_count"] += 1
        metrics["matches"].append({"id": expected["id"], "distance_px": round(best[1], 3)})

    finding_text = " ".join(
        normalize(finding.get("component")) + " " + normalize(finding.get("defect")) + " " + normalize(finding.get("evidence"))
        for finding in findings
        if isinstance(finding, dict)
    )
    false_positive_hits = [term for term in contract["falsePositiveTerms"] if term.lower() in finding_text]
    metrics["false_positive_count"] = len(false_positive_hits)
    if false_positive_hits:
        metrics["failures"].append("false-positives:" + ",".join(false_positive_hits))

    non_findings_text = " ".join(normalize(item) for item in answer.get("non_findings", []))
    for required in ["decorative", "disabled", "export", "timestamp"]:
        if required not in non_findings_text:
            metrics["failures"].append(f"non-finding-{required}")

    match_points = 80.0 * metrics["matched_count"] / len(contract["expectedFindings"])
    non_finding_penalty = 0 if all(required in non_findings_text for required in ["decorative", "disabled", "export", "timestamp"]) else 10
    false_positive_penalty = min(20, metrics["false_positive_count"] * 5)
    metrics["score_0_100"] = round(max(0.0, match_points + 20.0 - non_finding_penalty - false_positive_penalty), 3)
    if not metrics["failures"] and metrics["matched_count"] == len(contract["expectedFindings"]):
        metrics["verdict"] = "PASS"
    return metrics


def write_metrics(path: Path | None, metrics: dict):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "visual-review-oracle.json")
    errors: list[str] = []
    check_shape(root, contract, errors)
    check_changed_paths(args.changed_paths, contract, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N68 verifier PASS (bundle shape)")
        return 0

    if args.expect_start_state:
        answer = load_json(root / "candidate" / "answer.json")
        metrics = score_answer(answer, None, contract)
        if metrics["matched_count"] != 0 or metrics["verdict"] == "PASS":
            print("ERROR: start-state unexpectedly passes or partially matches", file=sys.stderr)
            return 1
        print("N68 verifier PASS (expected start-state failures present)")
        return 0

    answer_file = args.answer_file or (root / "candidate" / "answer.json")
    raw = answer_file.read_text(encoding="utf-8", errors="replace")
    answer, parse_error = extract_json(raw)
    metrics = score_answer(answer, parse_error, contract)
    write_metrics(args.metrics_out, metrics)
    if metrics["verdict"] != "PASS":
        for failure in metrics["failures"]:
            print(f"Failed invariant: {failure}", file=sys.stderr)
        print(f"N68 score: {metrics['score_0_100']} matched={metrics['matched_count']}/{metrics['expected_count']}", file=sys.stderr)
        return 1

    print("N68 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
