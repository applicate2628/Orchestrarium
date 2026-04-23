import argparse
import importlib
import json
import sys
from pathlib import Path


TOP_LEVEL = ["README.md", "candidate", "inputs", "oracle", "scenario.yaml", "verifiers"]
REQUIRED_FILES = [
    "candidate/README.md",
    "candidate/delivery-state.json",
    "candidate/review-response.json",
    "candidate/closure.json",
    "candidate/workspace/README.md",
    "candidate/workspace/src/releaseflow/__init__.py",
    "candidate/workspace/src/releaseflow/config.py",
    "candidate/workspace/src/releaseflow/planner.py",
    "candidate/workspace/src/releaseflow/executor.py",
    "candidate/workspace/src/releaseflow/report.py",
    "candidate/workspace/src/releaseflow/models.py",
    "candidate/workspace/src/releaseflow/store.py",
    "candidate/workspace/tests/test_releaseflow.py",
    "inputs/incident-log.md",
    "inputs/decoy-map.md",
    "inputs/review-feedback.md",
    "inputs/phases/01-intake-plan.md",
    "inputs/phases/02-implementation.md",
    "inputs/phases/03-review-response.md",
    "inputs/phases/04-final-reentry-closeout.md",
    "oracle/delivery-contract.json",
    "verifiers/check_scope.py",
    "verifiers/check_staged_delivery.py",
]


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def load_json(path, errors):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - verifier reports candidate state
        errors.append(f"Invalid JSON {path}: {exc}")
        return {}


def load_contract(root):
    return json.loads((root / "oracle" / "delivery-contract.json").read_text(encoding="utf-8"))


def check_bundle_shape(root, errors):
    actual_top = sorted(path.name for path in root.iterdir())
    require(actual_top == TOP_LEVEL, f"Top-level bundle entries drifted: {actual_top}", errors)
    for rel in REQUIRED_FILES:
        require((root / rel).exists(), f"Missing required file: {rel}", errors)

    contract = load_contract(root)
    scenario_text = (root / "scenario.yaml").read_text(encoding="utf-8")
    for rel in contract["requiredChangedPaths"]:
        require(rel in scenario_text, f"scenario.yaml missing required changed path: {rel}", errors)


def import_releaseflow(root):
    src = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src))
    for name in list(sys.modules):
        if name == "releaseflow" or name.startswith("releaseflow."):
            del sys.modules[name]
    return {
        "config": importlib.import_module("releaseflow.config"),
        "planner": importlib.import_module("releaseflow.planner"),
        "executor": importlib.import_module("releaseflow.executor"),
        "report": importlib.import_module("releaseflow.report"),
    }


def collect_runtime_failures(root):
    failures = []
    try:
        modules = import_releaseflow(root)
    except Exception as exc:  # noqa: BLE001 - verifier reports candidate behavior
        return [f"import-releaseflow:{exc}"]

    try:
        name, profile = modules["config"].select_profile(
            {
                "activeProfile": "prod",
                "legacyProfile": "staging",
                "profiles": {
                    "prod": {"parallelism": 2, "blockedEnvs": ["frozen"]},
                    "staging": {"parallelism": 1, "blockedEnvs": []},
                },
            }
        )
        if name != "prod" or profile.get("parallelism") != 2:
            failures.append("active-profile-wins")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"active-profile-wins:{exc}")

    plan = []
    try:
        changes = [
            {
                "changeId": "search-api",
                "sequence": 1,
                "targetEnv": "prod",
                "dependsOn": [],
                "summary": "old search rollout",
            },
            {
                "changeId": "billing-ui",
                "sequence": 5,
                "targetEnv": "prod",
                "dependsOn": ["search-api"],
                "summary": "billing depends on search",
            },
            {
                "changeId": "search-api",
                "sequence": 7,
                "targetEnv": "prod",
                "dependsOn": [],
                "summary": "latest search rollout",
            },
            {
                "changeId": "admin-freeze",
                "sequence": 9,
                "targetEnv": "frozen",
                "dependsOn": [],
                "summary": "blocked admin rollout",
            },
        ]
        profile = {"blockedEnvs": ["frozen"]}
        plan = modules["planner"].build_plan(changes, profile)
        ids = [item.get("changeId") for item in plan]
        by_id = {item.get("changeId"): item for item in plan}
        if "admin-freeze" in ids:
            failures.append("blocked-env-excluded")
        if by_id.get("search-api", {}).get("sequence") != 7:
            failures.append("latest-change-wins")
        if ids != ["search-api", "billing-ui"]:
            failures.append("dependency-order")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"planner-invariants:{exc}")

    try:
        ledger = {"applied": [], "audit": []}
        try:
            modules["executor"].execute_plan(plan, ledger, attempt=1, crash_after=1)
        except RuntimeError:
            pass
        modules["executor"].execute_plan(plan, ledger, attempt=2)
        applied_pairs = [(item.get("changeId"), item.get("targetEnv")) for item in ledger.get("applied", [])]
        if sorted(applied_pairs) != [("billing-ui", "prod"), ("search-api", "prod")]:
            failures.append("resume-idempotent")
        action_keys = [str(item.get("actionKey", "")) for item in ledger.get("applied", [])]
        if any("attempt" in key.lower() for key in action_keys):
            failures.append("resume-idempotent")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"resume-idempotent:{exc}")

    try:
        ledger = {
            "applied": [
                {"actionKey": "search-api:prod", "changeId": "search-api", "targetEnv": "prod"},
                {"actionKey": "billing-ui:prod", "changeId": "billing-ui", "targetEnv": "prod"},
            ],
            "audit": [
                {"event": "applied", "actionKey": "search-api:prod"},
                {"event": "applied", "actionKey": "billing-ui:prod"},
            ],
        }
        report = modules["report"].build_report(
            ledger,
            [{"message": "toast: stale staging change looked applied"}],
        )
        rendered = json.dumps(report, sort_keys=True)
        if report.get("reportSource") not in {"ledger-audit", "ledger"}:
            failures.append("report-from-ledger-audit")
        if report.get("appliedCount") != 2:
            failures.append("report-from-ledger-audit")
        if report.get("auditCount", 0) < 2:
            failures.append("report-from-ledger-audit")
        if "toast" in rendered or "stale staging" in rendered:
            failures.append("report-from-ledger-audit")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"report-from-ledger-audit:{exc}")

    return failures


def as_json_text(value):
    return json.dumps(value, sort_keys=True)


def list_field_contains(container, expected):
    if not isinstance(container, list):
        return False
    return expected in {str(item) for item in container}


def find_phase(delivery_state, phase_id):
    for item in delivery_state.get("phases", []):
        if not isinstance(item, dict):
            continue
        if item.get("id") == phase_id or item.get("phase") == phase_id or item.get("phaseId") == phase_id:
            return item
    return None


def collect_artifact_failures(root, contract):
    failures = []
    delivery = load_json(root / "candidate" / "delivery-state.json", failures)
    review = load_json(root / "candidate" / "review-response.json", failures)
    closure = load_json(root / "candidate" / "closure.json", failures)

    delivery_text = as_json_text(delivery)
    if contract["planFingerprint"] not in delivery_text:
        failures.append("phase-ledger-complete")
    for source_id in contract["expectedSourceIds"]:
        if source_id not in delivery_text:
            failures.append("phase-ledger-complete")
            break
    for stale_term in ["stale-plan.md", "legacy/report_old.py", "ui/status_badges.py"]:
        if stale_term not in delivery_text:
            failures.append("phase-ledger-complete")
            break
    for phase_id in contract["expectedPhaseIds"]:
        if find_phase(delivery, phase_id) is None:
            failures.append("phase-ledger-complete")
            break

    responses = review.get("responses", [])
    response_by_id = {}
    if isinstance(responses, list):
        for item in responses:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id") or item.get("reviewId")
            if item_id:
                response_by_id[item_id] = item
    for review_id, decision in contract["reviewDecisions"].items():
        item = response_by_id.get(review_id)
        if not item or str(item.get("decision", "")).lower() != decision:
            failures.append("review-response-complete")
            break
        owner = item.get("owner") or item.get("ownerPath") or item.get("runtimeOwnerPath")
        if not owner or not item.get("validationCue"):
            failures.append("review-response-complete")
            break

    closure_text = as_json_text(closure)
    if contract["planFingerprint"] not in closure_text:
        failures.append("closure-complete")
    changed_paths = closure.get("changedPaths")
    if sorted(changed_paths or []) != sorted(contract["requiredChangedPaths"]):
        failures.append("closure-complete")
    validation_text = as_json_text(closure.get("validation", []))
    if "python candidate/workspace/tests/test_releaseflow.py" not in validation_text:
        failures.append("closure-complete")
    if "residualRisk" not in closure:
        failures.append("closure-complete")

    test_text = (root / "candidate" / "workspace" / "tests" / "test_releaseflow.py").read_text(
        encoding="utf-8"
    )
    for marker in contract["testMarkers"]:
        if marker not in test_text:
            failures.append("tests-cover-required-invariants")
            break

    return failures


def check_forbidden_terms(root, contract, errors):
    scan_paths = [
        "candidate/workspace/src/releaseflow/config.py",
        "candidate/workspace/src/releaseflow/planner.py",
        "candidate/workspace/src/releaseflow/executor.py",
        "candidate/workspace/src/releaseflow/report.py",
        "candidate/workspace/tests/test_releaseflow.py",
    ]
    for rel in scan_paths:
        text = (root / rel).read_text(encoding="utf-8")
        lowered = text.lower()
        for term in contract["forbiddenCandidateTerms"]:
            if term.lower() in lowered:
                errors.append(f"Forbidden oracle/verifier term {term!r} appears in {rel}")


def run_completed(root, errors):
    contract = load_contract(root)
    runtime_failures = collect_runtime_failures(root)
    artifact_failures = collect_artifact_failures(root, contract)
    failures = runtime_failures + artifact_failures
    for failure in failures:
        errors.append(f"Failed invariant: {failure}")
    check_forbidden_terms(root, contract, errors)


def run_start_state(root, errors):
    contract = load_contract(root)
    failures = set(collect_runtime_failures(root) + collect_artifact_failures(root, contract))
    expected = {
        "active-profile-wins",
        "latest-change-wins",
        "blocked-env-excluded",
        "dependency-order",
        "resume-idempotent",
        "report-from-ledger-audit",
        "phase-ledger-complete",
        "review-response-complete",
        "closure-complete",
        "tests-cover-required-invariants",
    }
    missing = sorted(expected - failures)
    if missing:
        errors.append(f"Seeded start state no longer exposes expected failures: {missing}")


def main():
    parser = argparse.ArgumentParser(description="Check the N30 staged delivery bundle.")
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    args = parser.parse_args()

    root = Path.cwd()
    errors = []
    check_bundle_shape(root, errors)

    if not args.bundle_shape_only:
        if args.expect_start_state:
            run_start_state(root, errors)
        else:
            run_completed(root, errors)

    if errors:
        print("N30 verifier FAIL")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    mode = "bundle shape" if args.bundle_shape_only else "start state" if args.expect_start_state else "completed"
    print(f"N30 verifier PASS ({mode})")


if __name__ == "__main__":
    main()
