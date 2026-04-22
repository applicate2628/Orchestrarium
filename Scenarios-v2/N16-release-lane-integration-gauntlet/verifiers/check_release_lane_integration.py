#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import importlib
import json
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N16 release lane integration gauntlet.")
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
        if name == "releaseflow" or name.startswith("releaseflow."):
            del sys.modules[name]
    return importlib.import_module("releaseflow")


def req(id_, lane="prod", **kwargs):
    item = {
        "id": id_,
        "customer": kwargs.pop("customer", "acme"),
        "service": kwargs.pop("service", "api"),
        "version": kwargs.pop("version", "1.0"),
        "lane": lane,
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
            "balanced": {"freeze_lanes": [], "lane_order": ["canary", "prod"]},
            "emergency": {"freeze_lanes": [], "lane_order": ["prod", "canary"]},
            "default": {"freeze_lanes": [], "lane_order": ["canary", "prod"]},
        },
    }
    base.update(kwargs)
    return base


def keys_for(state, event_type="released"):
    return [event["key"] for event in state.ledger if event.get("type") == event_type]


def assert_equal(actual, expected, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def evaluate_invariants(root: Path):
    api = import_api(root)
    failures = []

    def case(case_id, fn):
        try:
            fn(api)
        except Exception as exc:  # noqa: BLE001 - verifier must report candidate behavior
            failures.append({"id": case_id, "detail": str(exc)})

    def active_profile_precedence(api):
        state = api.ReleaseState()
        run_config = config(
            profiles={
                "balanced": {"freeze_lanes": ["prod"], "lane_order": ["canary", "prod"]},
                "emergency": {"freeze_lanes": [], "lane_order": ["prod"]},
            }
        )
        api.run_release(state, run_config, [req("r1", "prod")])
        assert_equal(keys_for(state), [], "frozen prod ledger")
        assert_equal(api.summarize_state(state)["deferred"], 1, "frozen prod deferred")

    def request_input_immutability(api):
        state = api.ReleaseState()
        requests = [req("z", "canary"), req("a", "canary", service="worker")]
        original = copy.deepcopy(requests)
        api.run_release(state, config(activeProfile="default", legacyProfile=None), requests)
        assert_equal(requests, original, "request mutation")

    def semantic_dedupe_idempotency(api):
        state = api.ReleaseState()
        requests = [
            req("old", "canary", source="old-ticket", requested_at=1),
            req("new", "canary", source="new-ticket", requested_at=2),
        ]
        api.run_release(state, config(activeProfile="default", legacyProfile=None), copy.deepcopy(requests))
        api.run_release(state, config(activeProfile="default", legacyProfile=None), copy.deepcopy(requests))
        released = [event for event in state.ledger if event.get("type") == "released"]
        assert_equal(len(released), 1, "semantic release count")
        assert_equal(released[0]["source"], "new-ticket", "semantic winner")

    def dependency_order(api):
        state = api.ReleaseState()
        canary_key = "acme:api:2.0:canary"
        requests = [
            req("prod", "prod", version="2.0", priority=10, depends_on=[canary_key]),
            req("canary", "canary", version="2.0", priority=1),
        ]
        api.run_release(state, config(activeProfile="default", legacyProfile=None), requests)
        assert_equal(keys_for(state), [canary_key, "acme:api:2.0:prod"], "dependency release order")

    def canary_before_prod(api):
        state = api.ReleaseState()
        requests = [
            req("prod", "prod", version="3.0", priority=10),
            req("canary", "canary", version="3.0", priority=1),
        ]
        api.run_release(state, config(activeProfile="default", legacyProfile=None), requests)
        assert_equal(keys_for(state), ["acme:api:3.0:canary", "acme:api:3.0:prod"], "canary/prod order")

    def freeze_lane_deferred(api):
        state = api.ReleaseState()
        run_config = config(
            activeProfile="default",
            legacyProfile=None,
            profiles={"default": {"freeze_lanes": ["prod"], "lane_order": ["canary", "prod"]}},
        )
        api.run_release(state, run_config, [req("prod", "prod", version="4.0"), req("canary", "canary", version="4.0")])
        assert_equal(keys_for(state), ["acme:api:4.0:canary"], "freeze ledger")
        assert_equal(api.summarize_state(state)["deferred"], 1, "freeze deferred")

    def exactly_once_notifications(api):
        state = api.ReleaseState()
        requests = [req("r1", "canary", version="5.0")]
        api.run_release(state, config(activeProfile="default", legacyProfile=None), copy.deepcopy(requests))
        api.run_release(state, config(activeProfile="default", legacyProfile=None), copy.deepcopy(requests))
        assert_equal([item["key"] for item in state.notifications], ["acme:api:5.0:canary"], "exactly once notification")

    def rollback_current_group_only(api):
        state = api.ReleaseState()
        api.run_release(
            state,
            config(activeProfile="default", legacyProfile=None),
            [req("stable", "canary", version="g1", deployment_group="stable")],
        )
        api.run_release(
            state,
            config(activeProfile="default", legacyProfile=None),
            [req("new", "prod", version="g1", deployment_group="g1")],
            fail_group="g1",
        )
        released = [event["key"] for event in state.ledger if event.get("type") == "released"]
        rolled = [event["key"] for event in state.ledger if event.get("type") == "rolled-back"]
        assert_equal(released, ["acme:api:g1:canary"], "stable release preserved")
        assert_equal(rolled, ["acme:api:g1:prod"], "current group rolled back")

    def source_trace_preserved(api):
        state = api.ReleaseState()
        api.run_release(state, config(activeProfile="default", legacyProfile=None), [req("r1", "canary", source="ticket-123")])
        sources = [entry.get("source") for entry in state.audit]
        assert_equal(sources, ["ticket-123"], "audit source trace")

    def report_from_ledger_audit(api):
        state = api.ReleaseState()
        api.run_release(state, config(activeProfile="default", legacyProfile=None), [req("r1", "canary", source="ticket-456")])
        state.notifications.clear()
        summary = api.summarize_state(state)
        assert_equal(summary["released"], 1, "report released from ledger")
        assert_equal(summary["sources"], ["ticket-456"], "report source from audit")

    case("active-profile-precedence", active_profile_precedence)
    case("request-input-immutability", request_input_immutability)
    case("semantic-dedupe-idempotency", semantic_dedupe_idempotency)
    case("dependency-order", dependency_order)
    case("canary-before-prod", canary_before_prod)
    case("freeze-lane-deferred", freeze_lane_deferred)
    case("exactly-once-notifications", exactly_once_notifications)
    case("rollback-current-group-only", rollback_current_group_only)
    case("source-trace-preserved", source_trace_preserved)
    case("report-from-ledger-audit", report_from_ledger_audit)
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

    contract = load_json(root / "oracle" / "integration-contract.json")
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
                errors.append(f"Completed candidate still fails integration invariants: {rendered}")

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
    print(f"N16 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
