#!/usr/bin/env python3
"""V3LTA blind-audit verifier (F2, working-audit family).

Scores a wide-shallow single-aspect blind audit by RECALL AT A FIXED PRECISION FLOOR under an
identical enforced budget. The SCORE is recall (fraction of planted SQL-injection defects located),
GATED by a pre-registered precision floor: if precision < floor the run FAILS regardless of recall,
which punishes false-positive / decoy-following answers. Cost (tokens, wall clock) is NEVER divided
into the score -- there is no cost denominator (the A8 BLOCKER). Cost is reported ONLY as a DEFERRED,
ASSUMPTION-labeled diagnostic (I6).

Matching is purely location-based and deterministic: a candidate finding is a TRUE POSITIVE iff its
file basename matches a planted defect AND its cited line falls inside that defect's acceptable_lines
window. Any finding matching no defect window is a FALSE POSITIVE (this is how flagging a decoy or a
clean file, or citing a wrong line, drops precision below the floor). This verifier NEVER executes
candidate code and never needs an exec root -- the corpus is audit text only.

Exit codes:
  0  PASS           (bundle-shape, or scored: recall >= threshold AND precision >= floor)
  1  SCORED-FAIL    (quality FAIL: recall < threshold, or precision < floor)
  2  NOT-SCOREABLE  (missing/invalid answer.json, missing corpus/truth, parse failure -> NR)
  3  BUDGET-VIOLATION (telemetry present and outputTokens > cap -> disqualified, not scored)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXIT_PASS = 0
EXIT_SCORED_FAIL = 1
EXIT_NOT_SCOREABLE = 2
EXIT_BUDGET_VIOLATION = 3


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the V3LTA blind-audit bundle shape or score a completed audit answer."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root)
    parser.add_argument(
        "--candidate-root",
        type=Path,
        default=None,
        help="Alternate candidate directory (used by reference / probe candidates).",
    )
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    parser.add_argument(
        "--telemetry",
        type=Path,
        default=None,
        help="Optional summary.json to read telemetry from for the budget flag. "
        "If omitted, the verifier tries <bundle_root>.parent/meta/summary.json (I1 layout).",
    )
    return parser.parse_args()


# --- bundle shape -------------------------------------------------------------

def load_contract(bundle_root: Path):
    return json.loads(
        (bundle_root / "oracle" / "blind-audit-contract.json").read_text(encoding="utf-8")
    )


def load_truth(bundle_root: Path, contract: dict):
    return json.loads(
        (bundle_root / contract["corpus_truth_file"]).read_text(encoding="utf-8")
    )


def parse_simple_yaml(path: Path):
    data = {}
    current_list = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            data.setdefault(current_list, []).append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value == "":
            data[key] = []
            current_list = key
        elif value == "[]":
            data[key] = []
            current_list = None
        else:
            data[key] = value.strip('"')
            current_list = None
    return data


def top_level_yaml_keys(path: Path):
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


def check_bundle_shape(bundle_root: Path, contract: dict, errors: list):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)
    for relative_path in contract["required_bundle_files"]:
        require(
            (bundle_root / relative_path).exists(),
            f"Missing required bundle file: {relative_path}",
            errors,
        )

    corpus_dir = bundle_root / "inputs" / "corpus"
    corpus_files = sorted(corpus_dir.glob("h*.py")) if corpus_dir.exists() else []
    require(
        len(corpus_files) == contract["required_corpus_count"],
        f"Corpus file count mismatch: expected {contract['required_corpus_count']}, "
        f"got {len(corpus_files)}",
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
            parse_simple_yaml(scenario_path) == contract["expected_metadata"],
            "scenario.yaml metadata does not match V3LTA",
            errors,
        )


def check_changed_paths(changed_paths, allowed_paths, errors):
    allowed = set(allowed_paths)
    unexpected = sorted(
        {p.replace("\\", "/").strip("/") for p in changed_paths}
        - allowed
    )
    if unexpected:
        errors.append("Changed path outside the allowed change surface: " + ", ".join(unexpected))


# --- budget diagnostic --------------------------------------------------------

def resolve_telemetry(bundle_root: Path, explicit: Path | None):
    if explicit is not None:
        return explicit if explicit.exists() else None
    # I1 layout: meta/ is a sibling of the score bundle root.
    candidate = bundle_root.parent / "meta" / "summary.json"
    return candidate if candidate.exists() else None


def read_budget_state(telemetry_path: Path | None, contract: dict):
    """Return (state, detail) where state in {absent, within, over, unavailable}."""
    if telemetry_path is None:
        return "absent", "no telemetry summary.json found; budget assumed harness-enforced"
    try:
        summary = json.loads(telemetry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return "unavailable", f"telemetry unreadable: {exc}"
    telemetry = summary.get("telemetry") or {}
    out_tokens = telemetry.get("outputTokens")
    cap = contract["budget"]["budget_output_tokens_cap"]
    if out_tokens is None:
        return "unavailable", "telemetry.outputTokens is null"
    if out_tokens > cap:
        return "over", f"outputTokens={out_tokens} > cap={cap}"
    return "within", f"outputTokens={out_tokens} <= cap={cap}"


# --- scoring ------------------------------------------------------------------

def normalize_basename(file_value: str) -> str:
    return Path(str(file_value).replace("\\", "/")).name


def load_answer(candidate_root: Path, contract: dict):
    answer_path = candidate_root / "answer.json"
    if not answer_path.exists():
        return None, f"Missing candidate answer: {answer_path.name}"
    try:
        data = json.loads(answer_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"answer.json is invalid JSON: {exc}"
    if not isinstance(data, dict):
        return None, "answer.json top level is not an object"
    return data, None


def score_answer(answer: dict, truth: dict, contract: dict):
    """Return (result_dict, scoreable, message).

    scoreable=False signals NR (return code 2). Otherwise result_dict carries recall/precision.
    """
    ac = contract["answer_contract"]
    for key in ac["required_top_level"]:
        if key not in answer:
            return None, False, f"answer.json missing required key: {key}"
    if answer.get("aspect") != ac["aspect_must_equal"]:
        return None, False, (
            f"answer.json aspect {answer.get('aspect')!r} != required "
            f"{ac['aspect_must_equal']!r}"
        )
    findings = answer.get("findings")
    if not isinstance(findings, list):
        return None, False, "answer.json findings is not a list"

    # index the ground truth by basename -> list of (defect_id, acceptable_lines set)
    by_basename: dict[str, list] = {}
    for d in truth["defects"]:
        by_basename.setdefault(normalize_basename(d["file"]), []).append(
            (d["id"], set(d["acceptable_lines"]))
        )
    total_defects = len(truth["defects"])

    claimed_ids: set[str] = set()
    tp = 0
    fp = 0
    fp_examples: list[str] = []
    malformed = 0
    for idx, f in enumerate(findings, start=1):
        if not isinstance(f, dict) or "file" not in f or "line" not in f:
            malformed += 1
            continue
        try:
            line = int(f["line"])
        except (TypeError, ValueError):
            malformed += 1
            continue
        base = normalize_basename(f["file"])
        matched_id = None
        for defect_id, lines in by_basename.get(base, []):
            if line in lines:
                matched_id = defect_id
                break
        if matched_id is None:
            fp += 1
            if len(fp_examples) < 8:
                fp_examples.append(f"{base}:{line}")
        elif matched_id in claimed_ids:
            # duplicate hit on an already-claimed defect: ignore (neither TP nor FP)
            continue
        else:
            claimed_ids.add(matched_id)
            tp += 1

    # malformed findings count as FP (they are asserted findings that locate nothing)
    fp += malformed

    denom = tp + fp
    precision = 1.0 if denom == 0 else tp / denom
    recall = 0.0 if total_defects == 0 else tp / total_defects

    result = {
        "total_defects": total_defects,
        "true_positives": tp,
        "false_positives": fp,
        "malformed_findings": malformed,
        "false_negatives": total_defects - tp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "fp_examples": fp_examples,
        "unclaimed_defects": sorted(
            d["id"] for d in truth["defects"] if d["id"] not in claimed_ids
        ),
    }
    return result, True, None


def verdict(result: dict, contract: dict):
    floor = contract["score"]["precision_floor"]
    threshold = contract["score"]["recall_pass_threshold"]
    if result["precision"] < floor:
        return EXIT_SCORED_FAIL, (
            f"precision {result['precision']} < floor {floor} "
            f"(TP={result['true_positives']}, FP={result['false_positives']}) "
            f"-- false-positive / decoy-following answer punished below the precision floor"
        )
    if result["recall"] < threshold:
        return EXIT_SCORED_FAIL, (
            f"recall {result['recall']} < threshold {threshold} "
            f"(found {result['true_positives']}/{result['total_defects']}; "
            f"precision {result['precision']} >= floor {floor}) "
            f"-- insufficient breadth coverage under the fixed budget"
        )
    return EXIT_PASS, (
        f"recall {result['recall']} >= {threshold} AND precision {result['precision']} >= {floor}"
    )


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    candidate_root = (
        args.candidate_root.resolve() if args.candidate_root else bundle_root / "candidate"
    )
    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return EXIT_NOT_SCOREABLE

    errors: list[str] = []
    contract = load_contract(bundle_root)
    check_bundle_shape(bundle_root, contract, errors)
    if args.changed_paths:
        check_changed_paths(
            args.changed_paths, contract["expected_metadata"]["allowed_change_surface"], errors
        )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return EXIT_NOT_SCOREABLE

    if args.bundle_shape_only:
        print("V3LTA verifier PASS (bundle shape)")
        return EXIT_PASS

    # budget diagnostic (defense-in-depth demonstration of enforcement)
    telemetry_path = resolve_telemetry(bundle_root, args.telemetry)
    budget_state, budget_detail = read_budget_state(telemetry_path, contract)

    truth = load_truth(bundle_root, contract)
    answer, load_err = load_answer(candidate_root, contract)
    if answer is None:
        print(f"NOT-SCOREABLE (NR): {load_err}", file=sys.stderr)
        return EXIT_NOT_SCOREABLE

    result, scoreable, msg = score_answer(answer, truth, contract)
    if not scoreable:
        print(f"NOT-SCOREABLE (NR): {msg}", file=sys.stderr)
        return EXIT_NOT_SCOREABLE

    code, reason = verdict(result, contract)

    # Budget enforcement: an over-cap run is disqualified BEFORE the quality verdict is honored.
    if budget_state == "over":
        print(
            f"BUDGET-VIOLATION: {budget_detail} -- run disqualified (not scored). "
            f"[unscored recall={result['recall']}, precision={result['precision']}]",
            file=sys.stderr,
        )
        return EXIT_BUDGET_VIOLATION

    # Cost diagnostic is DEFERRED / ASSUMPTION-labeled (I6): reported, never scored.
    cost_line = _cost_diagnostic_line(telemetry_path, budget_state, budget_detail)

    print("V3LTA blind-audit score:")
    print(f"  recall              = {result['recall']}  (TP {result['true_positives']}/{result['total_defects']})")
    print(f"  precision           = {result['precision']}  (FP {result['false_positives']})")
    print(f"  precision_floor     = {contract['score']['precision_floor']}")
    print(f"  recall_pass_thresh  = {contract['score']['recall_pass_threshold']}")
    if result["fp_examples"]:
        print(f"  fp_examples         = {', '.join(result['fp_examples'])}")
    print(f"  budget              = {budget_state} ({budget_detail})")
    print(f"  {cost_line}")

    if code == EXIT_PASS:
        print(f"V3LTA verifier PASS (scored audit): {reason}")
    else:
        print(f"V3LTA verifier SCORED-FAIL: {reason}", file=sys.stderr)
    return code


def _cost_diagnostic_line(telemetry_path: Path | None, budget_state: str, budget_detail: str) -> str:
    prefix = "cost_diagnostic      = ASSUMPTION (UNVERIFIED, I6) -- deferred; NOT part of the score;"
    if telemetry_path is None:
        return f"{prefix} no telemetry available"
    try:
        summary = json.loads(telemetry_path.read_text(encoding="utf-8"))
        t = summary.get("telemetry") or {}
        return (
            f"{prefix} outputTokens={t.get('outputTokens')} wallClockMs={t.get('wallClockMs')} "
            f"costUsd={t.get('costUsd')} costSource={t.get('costSource')}"
        )
    except (json.JSONDecodeError, OSError):
        return f"{prefix} telemetry unreadable"


if __name__ == "__main__":
    raise SystemExit(main())
