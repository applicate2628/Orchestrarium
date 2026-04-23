import argparse
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    REPO_ROOT
    / "Scenarios-v2"
    / "N30-staged-delivery-reentry-gauntlet"
    / "oracle"
    / "delivery-contract.json"
)


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def case_root_from_arg(path):
    path = Path(path)
    if (path / "meta" / "summary.json").exists():
        return path
    if path.name == "meta" and (path / "summary.json").exists():
        return path.parent
    return path


def summary_for(case_root):
    return load_json(case_root / "meta" / "summary.json")


def verify_failed_invariants(summary):
    failed = []
    for result in summary.get("verificationResults", []):
        if result.get("passed"):
            continue
        log = Path(result.get("log", ""))
        if not log.exists():
            continue
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            marker = "Failed invariant: "
            if marker in line:
                failed.append(line.split(marker, 1)[1].strip())
    return sorted(set(failed))


def score_semantic(summary):
    if summary.get("verificationPassed"):
        return 30, []
    failed = verify_failed_invariants(summary)
    if not failed:
        return 0, ["verifier failed without invariant detail"]
    return max(0, 30 - 5 * len(failed)), [f"failed invariants: {', '.join(failed)}"]


def phase_rule_score(summary, contract):
    score = 0
    notes = []
    phases = {phase.get("phaseId"): phase for phase in summary.get("phases", [])}
    rules = contract["phasePathRules"]
    if len(phases) == len(contract["expectedPhaseIds"]):
        score += 3
    else:
        notes.append("phase count mismatch")

    per_phase_points = 12 / max(1, len(rules))
    for phase_id, rule in rules.items():
        phase = phases.get(phase_id)
        if not phase:
            notes.append(f"missing phase summary {phase_id}")
            continue
        changed = set(phase.get("benchmarkChangedPaths", []))
        allowed = set(rule["allowed"])
        required_any = set(rule["requiredAny"])
        if changed and changed <= allowed and changed & required_any:
            score += per_phase_points
        else:
            notes.append(f"{phase_id} path rule miss: changed={sorted(changed)}")
    return int(round(score)), notes


def text_contains_all(text, terms):
    return all(term in text for term in terms)


def score_artifacts(case_root, contract):
    delivery = load_json(case_root / "run" / "candidate" / "delivery-state.json") or {}
    review = load_json(case_root / "run" / "candidate" / "review-response.json") or {}
    closure = load_json(case_root / "run" / "candidate" / "closure.json") or {}

    delivery_text = json.dumps(delivery, sort_keys=True)
    review_text = json.dumps(review, sort_keys=True)
    closure_text = json.dumps(closure, sort_keys=True)

    resume = 0
    resume_notes = []
    if contract["planFingerprint"] in delivery_text:
        resume += 4
    else:
        resume_notes.append("plan fingerprint missing from delivery state")
    if contract["planFingerprint"] in closure_text:
        resume += 3
    else:
        resume_notes.append("plan fingerprint missing from closure")
    phases = delivery.get("phases", [])
    phase_ids = {
        item.get("id") or item.get("phase") or item.get("phaseId")
        for item in phases
        if isinstance(item, dict)
    }
    if set(contract["expectedPhaseIds"]) <= phase_ids:
        resume += 4
    else:
        resume_notes.append("phase ledger incomplete")
    if text_contains_all(delivery_text, contract["expectedSourceIds"]):
        resume += 4
    else:
        resume_notes.append("source ids incomplete")

    review_score = 0
    review_notes = []
    responses = review.get("responses", [])
    response_by_id = {
        (item.get("id") or item.get("reviewId")): item
        for item in responses
        if isinstance(item, dict) and (item.get("id") or item.get("reviewId"))
    }
    for review_id, decision in contract["reviewDecisions"].items():
        item = response_by_id.get(review_id)
        owner = None if not item else item.get("owner") or item.get("ownerPath") or item.get("runtimeOwnerPath")
        if item and str(item.get("decision", "")).lower() == decision and owner and item.get("validationCue"):
            review_score += 2
        else:
            review_notes.append(f"review decision miss {review_id}")

    stale_score = 0
    stale_terms = ["stale-plan.md", "legacy/report_old.py", "ui/status_badges.py"]
    if text_contains_all(delivery_text, stale_terms) and "reject" in delivery_text.lower():
        stale_score = 5
    else:
        resume_notes.append("stale-source rejection incomplete")

    closure_paths = closure.get("changedPaths") or []
    closure_exact = sorted(closure_paths) == sorted(contract["requiredChangedPaths"])

    return {
        "resume": min(15, resume),
        "review": min(10, review_score),
        "stale": stale_score,
        "closure_exact_paths": closure_exact,
        "notes": resume_notes + review_notes,
    }


def score_tests(case_root, contract, changed):
    test_path = case_root / "run" / "candidate" / "workspace" / "tests" / "test_releaseflow.py"
    if not test_path.exists():
        return 0, ["test file missing"]
    text = test_path.read_text(encoding="utf-8", errors="replace")
    if "candidate/workspace/tests/test_releaseflow.py" not in changed:
        return 2, ["tests not changed"]
    missing = [marker for marker in contract["testMarkers"] if marker not in text]
    if missing:
        return 3, [f"missing test markers: {', '.join(missing)}"]
    return 5, []


def output_bytes(summary):
    total = 0
    missing = 0
    for phase in summary.get("phases", []):
        value = phase.get("outputBytes")
        if isinstance(value, int):
            total += value
        else:
            missing += 1
    return total, missing


def score_time(summary):
    elapsed = sum(float(phase.get("elapsedSeconds") or 0) for phase in summary.get("phases", []))
    if elapsed <= 900:
        return 5, elapsed
    if elapsed <= 1800:
        return 3, elapsed
    return 1, elapsed


def score_output(summary):
    total, missing = output_bytes(summary)
    if missing:
        return 0, total, [f"{missing} phase outputs missing"]
    if total <= 40000:
        return 5, total, []
    if total <= 120000:
        return 3, total, []
    return 1, total, []


def score_row(case_root, contract):
    summary = summary_for(case_root)
    if not summary:
        return {
            "row": case_root.name,
            "binary": "RUNTIME-FAIL",
            "scoreability": "runtime-no-summary",
            "rubric": 0,
            "notes": ["missing staged summary.json"],
        }

    row = summary.get("rowId", case_root.name)
    wrapper_ok = summary.get("wrapperExitCode") == 0
    binary = "PASS" if wrapper_ok and summary.get("verificationPassed") else "FAIL" if wrapper_ok else "RUNTIME-FAIL"
    scoreability = "scoreable" if wrapper_ok else "runtime-phase-fail"

    changed = list(summary.get("benchmarkChangedPaths", []))
    notes = []

    semantic, semantic_notes = score_semantic(summary)
    phase, phase_notes = phase_rule_score(summary, contract)
    artifacts = score_artifacts(case_root, contract)
    tests, test_notes = score_tests(case_root, contract, changed)

    patch = 10 if sorted(changed) == sorted(contract["requiredChangedPaths"]) and artifacts["closure_exact_paths"] else 0
    if patch == 0:
        notes.append("patch budget mismatch")

    time_score, elapsed = score_time(summary)
    output_score, output_size, output_notes = score_output(summary)

    notes.extend(semantic_notes)
    notes.extend(phase_notes)
    notes.extend(artifacts["notes"])
    notes.extend(test_notes)
    notes.extend(output_notes)

    rubric = semantic + phase + artifacts["resume"] + artifacts["review"] + patch + tests + time_score + output_score + artifacts["stale"]

    return {
        "row": row,
        "binary": binary,
        "scoreability": scoreability,
        "rubric": rubric,
        "semantic": semantic,
        "phase": phase,
        "resume": artifacts["resume"],
        "review": artifacts["review"],
        "patch": patch,
        "tests": tests,
        "time": time_score,
        "output": output_score,
        "stale": artifacts["stale"],
        "elapsedSeconds": round(elapsed, 3),
        "outputBytes": output_size,
        "changedCount": len(changed),
        "changedPaths": changed,
        "notes": notes,
        "summaryPath": str(case_root / "meta" / "summary.json"),
    }


def print_table(rows):
    headers = [
        "Row",
        "Binary",
        "Scoreability",
        "Rubric",
        "Semantic",
        "Phase",
        "Resume",
        "Review",
        "Patch",
        "Tests",
        "Time",
        "Output",
        "Stale",
        "Elapsed",
        "Bytes",
        "Notes",
    ]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        notes = "; ".join(row.get("notes", []))
        values = [
            row.get("row"),
            row.get("binary"),
            row.get("scoreability"),
            row.get("rubric"),
            row.get("semantic"),
            row.get("phase"),
            row.get("resume"),
            row.get("review"),
            row.get("patch"),
            row.get("tests"),
            row.get("time"),
            row.get("output"),
            row.get("stale"),
            row.get("elapsedSeconds"),
            row.get("outputBytes"),
            notes,
        ]
        print("| " + " | ".join(str(value) for value in values) + " |")


def main():
    parser = argparse.ArgumentParser(description="Score N30 staged delivery runs.")
    parser.add_argument("case_roots", nargs="+")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    contract = load_json(CONTRACT_PATH)
    rows = [score_row(case_root_from_arg(path), contract) for path in args.case_roots]
    print_table(rows)

    payload = {
        "scenario": "N30",
        "surface": "E20",
        "contract": str(CONTRACT_PATH),
        "rows": rows,
    }
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
