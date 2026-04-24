#!/usr/bin/env python3

from __future__ import annotations

import copy
import importlib
import json
import subprocess
import sys
from pathlib import Path
import argparse


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N55 incident compact operator-budget gauntlet.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
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
    for path in contract["required_bundle_paths"]:
        require((root / path).exists(), f"Missing required bundle path: {path}", errors)


def import_api(root: Path):
    src_root = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src_root))
    for name in list(sys.modules):
        if name == "deploygrid" or name.startswith("deploygrid."):
            del sys.modules[name]
    return importlib.import_module("deploygrid")


def req(id_, lane="prod", **kwargs):
    item = {
        "id": id_,
        "tenant": kwargs.pop("tenant", "acme"),
        "service": kwargs.pop("service", "api"),
        "version": kwargs.pop("version", "1.0"),
        "lane": lane,
        "window": kwargs.pop("window", "morning"),
        "priority": kwargs.pop("priority", 1),
        "source": kwargs.pop("source", id_),
        "depends_on": kwargs.pop("depends_on", []),
        "deployment_group": kwargs.pop("deployment_group", id_),
        "requested_at": kwargs.pop("requested_at", 1),
    }
    item.update(kwargs)
    return item


def config(**kwargs):
    base = {
        "activeProfile": "balanced",
        "legacyProfile": "emergency",
        "profiles": {
            "balanced": {"freeze": [], "lane_order": ["canary", "prod"]},
            "emergency": {"freeze": [], "lane_order": ["prod", "canary"]},
            "default": {"freeze": [], "lane_order": ["canary", "prod"]},
        },
    }
    base.update(kwargs)
    return base


def key(request):
    return f"{request['tenant']}:{request['service']}:{request['version']}:{request['lane']}:{request['window']}"


def released_keys(state):
    return [event["key"] for event in state.ledger if event.get("type") == "released"]


def rolled_keys(state):
    return [event["key"] for event in state.ledger if event.get("type") == "rolled-back"]


def assert_equal(actual, expected, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def require_terms(text: str, terms: list[str], label: str):
    missing = [term for term in terms if term.lower() not in text.lower()]
    if missing:
        raise AssertionError(f"{label}: missing {', '.join(missing)}")


def evaluate_reconciliation_note(root: Path):
    failures = []
    note_path = root / "candidate" / "reconciliation-note.md"
    text = note_path.read_text(encoding="utf-8", errors="replace") if note_path.exists() else ""

    def case(case_id, fn):
        try:
            fn(text)
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": case_id, "detail": str(exc)})

    def source_arbitration_note(text):
        require_terms(
            text,
            ["INC-742", "activeProfile", "authoritative", "legacyProfile", "fallback"],
            "source arbitration",
        )

    def stale_source_rejected(text):
        require_terms(text, ["reject", "UI", "legacy", "notification"], "stale-source rejection")
        forbidden_acceptance = [
            "legacyProfile should win",
            "legacyProfile overrides activeProfile",
            "UI label fix accepted",
            "counted from notifications",
        ]
        for phrase in forbidden_acceptance:
            if phrase.lower() in text.lower():
                raise AssertionError(f"stale direction accepted: {phrase}")

    def review_response_note(text):
        require_terms(text, ["R1", "R2", "R3", "R4", "R5"], "review response ids")
        require_terms(text, ["api.py", "source", "retry", "validation"], "review response content")

    def validation_evidence_note(text):
        if not any(
            marker.lower() in text.lower()
            for marker in ["check_incident_integration_repair.py", "unittest discover", "test_deploygrid.py"]
        ):
            raise AssertionError("validation evidence must name verifier or test command")

    case("source-arbitration-note", source_arbitration_note)
    case("stale-source-rejected", stale_source_rejected)
    case("review-response-note", review_response_note)
    case("validation-evidence-note", validation_evidence_note)
    return failures


def evaluate_invariants(root: Path):
    api = import_api(root)
    failures = []

    def case(case_id, fn):
        try:
            fn(api)
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": case_id, "detail": str(exc)})

    def active_profile_precedence(api):
        state = api.DeployState()
        run_config = config(
            profiles={
                "balanced": {"freeze": [{"tenant": "acme", "lane": "prod", "window": "morning"}], "lane_order": ["canary", "prod"]},
                "emergency": {"freeze": [], "lane_order": ["prod"]},
            }
        )
        api.run_deploy(state, run_config, [req("r1", "prod")])
        assert_equal(released_keys(state), [], "active profile freeze")
        assert_equal(api.summarize_state(state)["deferred"], 1, "deferred count")

    def request_input_immutability(api):
        state = api.DeployState()
        requests = [req("z", "canary"), req("a", "canary", service="worker")]
        run_config = config(activeProfile="default", legacyProfile=None)
        original_requests = copy.deepcopy(requests)
        original_config = copy.deepcopy(run_config)
        api.run_deploy(state, run_config, requests)
        assert_equal(requests, original_requests, "request mutation")
        assert_equal(run_config, original_config, "config mutation")

    def semantic_dedupe_latest_wins(api):
        state = api.DeployState()
        requests = [
            req("old", "canary", source="old-ticket", requested_at=1),
            req("new", "canary", source="new-ticket", requested_at=2),
        ]
        api.run_deploy(state, config(activeProfile="default", legacyProfile=None), copy.deepcopy(requests))
        api.run_deploy(state, config(activeProfile="default", legacyProfile=None), copy.deepcopy(requests))
        released = [event for event in state.ledger if event.get("type") == "released"]
        assert_equal(len(released), 1, "semantic release count")
        assert_equal(released[0]["source"], "new-ticket", "latest source winner")
        superseded_sources = [entry.get("source") for entry in state.audit if entry.get("action") == "superseded"]
        assert_equal(superseded_sources, ["old-ticket"], "superseded audit source")

    def dependency_order(api):
        state = api.DeployState()
        canary_key = "acme:api:2.0:canary:morning"
        requests = [
            req("prod", "prod", version="2.0", priority=10, depends_on=[canary_key]),
            req("canary", "canary", version="2.0", priority=1),
        ]
        api.run_deploy(state, config(activeProfile="default", legacyProfile=None), requests)
        assert_equal(released_keys(state), [canary_key, "acme:api:2.0:prod:morning"], "dependency release order")

    def cycle_blocked(api):
        state = api.DeployState()
        a_key = "acme:api:cy:canary:morning"
        b_key = "acme:worker:cy:canary:morning"
        requests = [
            req("a", "canary", version="cy", depends_on=[b_key]),
            req("b", "canary", service="worker", version="cy", depends_on=[a_key]),
        ]
        api.run_deploy(state, config(activeProfile="default", legacyProfile=None), requests)
        summary = api.summarize_state(state)
        assert_equal(released_keys(state), [], "cycle releases")
        assert_equal(summary["blocked"], 2, "cycle blocked count")
        assert_equal(summary["cycles"], 1, "cycle report count")

    def canary_before_prod(api):
        state = api.DeployState()
        requests = [
            req("prod", "prod", version="3.0", priority=10),
            req("canary", "canary", version="3.0", priority=1),
        ]
        api.run_deploy(state, config(activeProfile="default", legacyProfile=None), requests)
        assert_equal(released_keys(state), ["acme:api:3.0:canary:morning", "acme:api:3.0:prod:morning"], "canary/prod order")
        missing = api.DeployState()
        api.run_deploy(missing, config(activeProfile="default", legacyProfile=None), [req("prod-only", "prod", version="3.1")])
        assert_equal(released_keys(missing), [], "prod without canary release")
        assert_equal(api.summarize_state(missing)["blocked"], 1, "prod without canary blocked")

    def frozen_scope_deferred(api):
        state = api.DeployState()
        run_config = config(
            activeProfile="default",
            legacyProfile=None,
            profiles={"default": {"freeze": [{"tenant": "acme", "lane": "prod", "window": "night"}], "lane_order": ["canary", "prod"]}},
        )
        api.run_deploy(state, run_config, [req("prod", "prod", version="4.0", window="night"), req("canary", "canary", version="4.0", window="night")])
        assert_equal(released_keys(state), ["acme:api:4.0:canary:night"], "freeze ledger")
        assert_equal(api.summarize_state(state)["deferred"], 1, "freeze deferred")

    def idempotent_repeat(api):
        state = api.DeployState()
        requests = [req("r1", "canary", version="5.0")]
        api.run_deploy(state, config(activeProfile="default", legacyProfile=None), copy.deepcopy(requests))
        api.run_deploy(state, config(activeProfile="default", legacyProfile=None), copy.deepcopy(requests))
        assert_equal(released_keys(state), ["acme:api:5.0:canary:morning"], "idempotent ledger")
        assert_equal([item["key"] for item in state.notifications], ["acme:api:5.0:canary:morning"], "idempotent notifications")

    def crash_resume_no_replay(api):
        state = api.DeployState()
        requests = [req("canary", "canary", version="6.0"), req("prod", "prod", version="6.0")]
        try:
            api.run_deploy(
                state,
                config(activeProfile="default", legacyProfile=None),
                copy.deepcopy(requests),
                crash_after_key="acme:api:6.0:canary:morning",
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected simulated crash")
        api.run_deploy(state, config(activeProfile="default", legacyProfile=None), copy.deepcopy(requests))
        assert_equal(released_keys(state), ["acme:api:6.0:canary:morning", "acme:api:6.0:prod:morning"], "resume ledger")
        assert_equal([item["key"] for item in state.notifications], ["acme:api:6.0:canary:morning", "acme:api:6.0:prod:morning"], "resume notifications")

    def rollback_current_attempt_only(api):
        state = api.DeployState()
        api.run_deploy(state, config(activeProfile="default", legacyProfile=None), [req("stable", "canary", version="stable", deployment_group="stable")])
        api.run_deploy(
            state,
            config(activeProfile="default", legacyProfile=None),
            [req("canary", "canary", version="7.0", deployment_group="g7"), req("prod", "prod", version="7.0", deployment_group="g7")],
            fail_group="g7",
        )
        assert_equal(released_keys(state), ["acme:api:stable:canary:morning"], "stable release preserved")
        assert_equal(rolled_keys(state), ["acme:api:7.0:canary:morning", "acme:api:7.0:prod:morning"], "current attempt rolled back")

    def source_trace_preserved(api):
        state = api.DeployState()
        api.run_deploy(state, config(activeProfile="default", legacyProfile=None), [req("r1", "canary", source="ticket-123")])
        sources = [entry.get("source") for entry in state.audit if entry.get("action") == "released"]
        assert_equal(sources, ["ticket-123"], "audit source trace")

    def report_from_ledger_audit(api):
        state = api.DeployState()
        api.run_deploy(state, config(activeProfile="default", legacyProfile=None), [req("r1", "canary", source="ticket-456")])
        state.notifications.clear()
        summary = api.summarize_state(state)
        assert_equal(summary["released"], 1, "report released from ledger")
        assert_equal(summary["sources"], ["ticket-456"], "report source from audit")

    case("active-profile-precedence", active_profile_precedence)
    case("request-input-immutability", request_input_immutability)
    case("semantic-dedupe-latest-wins", semantic_dedupe_latest_wins)
    case("dependency-order", dependency_order)
    case("cycle-blocked", cycle_blocked)
    case("canary-before-prod", canary_before_prod)
    case("frozen-scope-deferred", frozen_scope_deferred)
    case("idempotent-repeat", idempotent_repeat)
    case("crash-resume-no-replay", crash_resume_no_replay)
    case("rollback-current-attempt-only", rollback_current_attempt_only)
    case("source-trace-preserved", source_trace_preserved)
    case("report-from-ledger-audit", report_from_ledger_audit)
    failures.extend(evaluate_reconciliation_note(root))
    return failures


def run_direct_tests(root: Path, errors: list[str]):
    workspace = root / "candidate" / "workspace"
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
        errors.append(f"Direct tests failed: {output or 'no output'}")


def check_no_oracle_hardcoding(root: Path, contract: dict, errors: list[str]):
    paths = contract["expected_metadata"]["allowed_change_surface"]
    terms = [term.lower() for term in contract["prohibited_candidate_terms"]]
    for rel_path in paths:
        text = (root / rel_path).read_text(encoding="utf-8").lower()
        for term in terms:
            if term in text:
                errors.append(f"Candidate file {rel_path} contains prohibited oracle/case literal: {term}")


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list[str] = []

    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "incident-repair-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        failures = evaluate_invariants(root)
        failure_ids = sorted(failure["id"] for failure in failures)
        if args.expect_start_state:
            expected = sorted(contract["expected_start_state_failures"])
            require(failure_ids == expected, f"Expected start-state failures {expected}, found {failure_ids}", errors)
        else:
            run_direct_tests(root, errors)
            check_no_oracle_hardcoding(root, contract, errors)
            if failures:
                rendered = json.dumps(failures, indent=2, sort_keys=True)
                errors.append(f"Completed candidate still fails incident repair invariants: {rendered}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        mode = "bundle shape"
    elif args.expect_start_state:
        mode = "start state"
    else:
        mode = "completed run"
    print(f"N55 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
