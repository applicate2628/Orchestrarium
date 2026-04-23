#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N39 staged systems/toolchain reentry gauntlet.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def import_stagegate(root: Path):
    src_root = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src_root))
    for name in list(sys.modules):
        if name == "stagegate" or name.startswith("stagegate."):
            del sys.modules[name]
    return importlib.import_module("stagegate")


def cfg():
    return {
        "activeChannel": "release-linux",
        "legacyChannel": "debug-windows",
        "channels": {
            "release-linux": {"stage_root": "stage/release", "toolchain_revision": "clang-18.1"},
            "debug-windows": {"stage_root": "stage/windows", "toolchain_revision": "msvc-old"},
            "default": {"stage_root": "stage/default", "toolchain_revision": "default-tool"},
        },
    }


def request(api, artifact_id, **kwargs):
    return api.StageRequest(
        artifact_id=artifact_id,
        channel=kwargs.pop("channel", "release-linux"),
        source_hash=kwargs.pop("source_hash", f"hash-{artifact_id}"),
        features=tuple(kwargs.pop("features", ())),
        env_tokens=tuple(kwargs.pop("env_tokens", ())),
        depends_on=tuple(kwargs.pop("depends_on", ())),
        priority=kwargs.pop("priority", 0),
        source=kwargs.pop("source", f"ticket-{artifact_id}"),
        workspace=kwargs.pop("workspace", "/workspace"),
    )


def assert_equal(actual, expected, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def evaluate_invariants(root: Path):
    api = import_stagegate(root)
    recovery = importlib.import_module("stagegate.recovery")
    failures = []

    def case(case_id, fn):
        try:
            fn(api)
        except Exception as exc:  # noqa: BLE001 - verifier reports candidate behavior
            failures.append({"id": case_id, "detail": str(exc)})

    def active_channel_precedence(api):
        state = api.StageState()
        events = api.run_stagegate(state, cfg(), [request(api, "core", source_hash="same")])
        assert_equal(events[0]["stage_root"], "stage/release", "active channel staging root")
        if "clang-18.1" not in events[0]["fingerprint"]:
            raise AssertionError(f"active channel toolchain missing from fingerprint: {events[0]['fingerprint']}")
        if "msvc-old" in events[0]["fingerprint"]:
            raise AssertionError(f"legacy toolchain leaked into fingerprint: {events[0]['fingerprint']}")

    def valid_env_override(api):
        state = api.StageState()
        events = api.run_stagegate(
            state,
            cfg(),
            [request(api, "core", source_hash="same")],
            env={"STAGEGATE_ROOT": "R:\\stagecache\\roots\\"},
        )
        assert_equal(events[0]["stage_root"], "R:/stagecache/roots", "valid env root")

    def invalid_env_fallback(api):
        state = api.StageState()
        events = api.run_stagegate(
            state,
            cfg(),
            [request(api, "core", source_hash="same")],
            env={"STAGEGATE_ROOT": "relative/stage"},
        )
        assert_equal(events[0]["stage_root"], "stage/release", "invalid env fallback")

    def dependency_order(api):
        state = api.StageState()
        requests = [
            request(api, "ui-bundle", depends_on=("core-lib",), priority=90, source="ticket-ui"),
            request(api, "core-lib", priority=1, source="ticket-core"),
        ]
        api.run_stagegate(state, cfg(), requests)
        built = [event["artifact_id"] for event in state.ledger if event["type"] == "staged"]
        assert_equal(built, ["core-lib", "ui-bundle"], "dependency order")

    def fingerprint_portable(api):
        state = api.StageState()
        left = request(
            api,
            "portable",
            source_hash="h",
            features=("zlib", "ssl"),
            env_tokens=("CC=clang", "MODE=rel"),
            workspace="C:/tmp/work-a",
        )
        right = request(
            api,
            "portable",
            source_hash="h",
            features=("ssl", "zlib"),
            env_tokens=("MODE=rel", "CC=clang"),
            workspace="/var/tmp/work-b",
        )
        api.run_stagegate(state, cfg(), [left])
        api.run_stagegate(state, cfg(), [right])
        fingerprints = [event["fingerprint"] for event in state.ledger]
        assert_equal(len(set(fingerprints)), 1, "portable fingerprint equality")
        assert_equal([event["type"] for event in state.ledger], ["staged", "cache-restore"], "portable cache restore")
        bad_fragments = ["C:/tmp", "/var/tmp", "work-a", "work-b"]
        leaked = [fragment for fragment in bad_fragments if fragment in fingerprints[0]]
        if leaked:
            raise AssertionError(f"workspace path leaked into fingerprint: {leaked}")

    def mode_conflict_rejected(api):
        conflict_sets = [("signed", "unsigned-dev"), ("asan", "release-fast")]
        for features in conflict_sets:
            state = api.StageState()
            try:
                api.run_stagegate(state, cfg(), [request(api, "bad", features=features)])
            except ValueError:
                continue
            raise AssertionError(f"conflict was not rejected: {features}")

    def lease_release_on_failure(api):
        state = api.StageState()
        try:
            api.run_stagegate(state, cfg(), [request(api, "core", source="ticket-core")], fail_artifact="core")
        except RuntimeError:
            pass
        assert_equal(state.active_leases, set(), "active leases after failure")
        assert_equal([event["type"] for event in state.ledger], ["failed"], "failure ledger")
        assert_equal(state.ledger[0].get("source"), "ticket-core", "failure source trace")

    def cache_restore_source_trace(api):
        state = api.StageState()
        first = request(api, "cacheable", source_hash="h-cache", source="ticket-cache")
        api.run_stagegate(state, cfg(), [first])
        second = request(api, "cacheable", source_hash="h-cache", source="ticket-rerun")
        api.run_stagegate(state, cfg(), [second])
        assert_equal([event["type"] for event in state.ledger], ["staged", "cache-restore"], "cache restore event")
        assert_equal([event.get("source") for event in state.ledger], ["ticket-cache", "ticket-rerun"], "cache source trace")
        assert_equal(state.ledger[1].get("reason"), "fingerprint cache hit", "cache restore reason")

    def summary_source_trace(api):
        state = api.StageState()
        api.run_stagegate(state, cfg(), [request(api, "base", source="ticket-base")])
        api.run_stagegate(state, cfg(), [request(api, "base", source_hash="hash-base", source="ticket-base-rerun")])
        try:
            api.run_stagegate(state, cfg(), [request(api, "bad", source="ticket-fail")], fail_artifact="bad")
        except RuntimeError:
            pass
        summary = api.summarize_state(state)
        assert_equal(summary["sources"], ["ticket-base", "ticket-base-rerun", "ticket-fail"], "summary source trace")
        decisions = [(item["artifact_id"], item["type"], item["source"]) for item in summary["decisions"]]
        assert_equal(
            decisions,
            [("base", "staged", "ticket-base"), ("base", "cache-restore", "ticket-base-rerun"), ("bad", "failed", "ticket-fail")],
            "summary decisions",
        )

    def recovery_source_arbitration(api):
        state = api.StageState()
        packet = recovery.resume_from_checkpoint(
            state,
            {"source": "candidate/workspace/docs/stale-staging-runbook.md", "primary_task": "N39"},
            [
                {
                    "id": "S1",
                    "path": "Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md",
                    "current": True,
                },
                {"id": "ST1", "path": "candidate/workspace/docs/stale-staging-runbook.md", "current": False},
                {"id": "ST2", "path": "candidate/stale-results/old-winner-table.md", "current": False},
            ],
        )
        assert_equal(
            packet["source"],
            "Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md",
            "current source selected",
        )
        decisions = getattr(state, "recovery_decisions", [])
        stale_ids = {item.get("source_id") for item in decisions if item.get("classification") == "stale-rejected"}
        if not {"ST1", "ST2"} <= stale_ids:
            raise AssertionError(f"stale source rejection missing: {decisions}")

    def resume_continuity(api):
        state = api.StageState()
        packet = recovery.resume_from_checkpoint(
            state,
            {"source": "old-winner-table.md", "primary_task": "N39"},
            [
                {
                    "id": "S2",
                    "path": "Work/next-upgraded-pack/Planning/next-phase/hardening-wave-roadmap-2026-04-22.md",
                    "current": True,
                }
            ],
        )
        assert_equal(packet["owner"], "$lead", "resume owner")
        assert_equal(packet["primary_task"], "N39", "primary task continuity")
        if "Resume staged systems toolchain recovery" not in packet.get("visible_return_cue", ""):
            raise AssertionError(f"visible return cue missing: {packet}")

    def runtime_failure_classification(api):
        expected = {
            "quota": "REQUEUE",
            "timeout": "RUNTIME-FAIL",
            "route": "ROUTE-FAIL",
            "verifier": "FAIL",
        }
        for kind, status in expected.items():
            assert_equal(recovery.classify_runtime_failure({"kind": kind}), status, f"runtime classification {kind}")

    case("active-channel-precedence", active_channel_precedence)
    case("valid-env-override", valid_env_override)
    case("invalid-env-fallback", invalid_env_fallback)
    case("dependency-order", dependency_order)
    case("fingerprint-portable", fingerprint_portable)
    case("mode-conflict-rejected", mode_conflict_rejected)
    case("lease-release-on-failure", lease_release_on_failure)
    case("cache-restore-source-trace", cache_restore_source_trace)
    case("summary-source-trace", summary_source_trace)
    case("recovery-source-arbitration", recovery_source_arbitration)
    case("resume-continuity", resume_continuity)
    case("runtime-failure-classification", runtime_failure_classification)
    return failures


def contains_all(text: str, markers: list[str]):
    lower = text.lower()
    return all(marker.lower() in lower for marker in markers)


def changed_paths_match_scope(changed_paths: list[str], contract: dict):
    observed = {path.replace("\\", "/") for path in changed_paths}
    allowed = set(contract["allowedChangedPaths"])
    required_core = set(contract["requiredChangedCorePaths"])
    any_groups = [set(group) for group in contract.get("requiredChangedAnyOf", [])]

    missing_core = sorted(required_core - observed)
    extra = sorted(observed - allowed)
    if missing_core:
        return False, f"missing required core changed paths: {missing_core}"
    for group in any_groups:
        if not observed & group:
            return False, f"missing required one-of changed paths: {sorted(group)}"
    if extra:
        return False, f"changed paths outside bounded surface: {extra}"
    return True, ""


def evaluate_ledger(root: Path, contract: dict):
    try:
        ledger = load_json(root / "candidate" / "workspace" / "implementation-ledger.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "ledger-complete", "detail": f"invalid JSON: {exc}"}]
    text = json.dumps(ledger, sort_keys=True)
    phase_ids = {item.get("id") or item.get("phaseId") for item in ledger.get("phases", []) if isinstance(item, dict)}
    phase_owners = [
        item for item in ledger.get("phases", [])
        if isinstance(item, dict) and (item.get("owner") or item.get("ownerPath"))
    ]
    if ledger.get("contractId") != contract["contractId"]:
        return [{"id": "ledger-complete", "detail": "contractId mismatch"}]
    if ledger.get("planFingerprint") != contract["planFingerprint"]:
        return [{"id": "ledger-complete", "detail": "plan fingerprint missing"}]
    if set(contract["expectedPhaseIds"]) - phase_ids or len(phase_owners) < len(contract["expectedPhaseIds"]):
        return [{"id": "ledger-complete", "detail": "phase ids or owners incomplete"}]
    if not contains_all(text, contract["expectedSourceIds"]):
        return [{"id": "ledger-complete", "detail": "source ids incomplete"}]
    if not contains_all(text, contract["requiredLedgerMarkers"]):
        return [{"id": "ledger-complete", "detail": "required ledger markers incomplete"}]
    return []


def evaluate_closure(root: Path, contract: dict):
    try:
        closure = load_json(root / "candidate" / "workspace" / "closure.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "closure-complete", "detail": f"invalid JSON: {exc}"}]
    text = json.dumps(closure, sort_keys=True)
    if closure.get("contractId") != contract["contractId"]:
        return [{"id": "closure-complete", "detail": "contractId mismatch"}]
    if closure.get("planFingerprint") != contract["planFingerprint"]:
        return [{"id": "closure-complete", "detail": "plan fingerprint missing"}]
    matches_scope, detail = changed_paths_match_scope(closure.get("changedPaths", []), contract)
    if not matches_scope:
        return [{"id": "closure-complete", "detail": detail}]
    if not closure.get("outcome") or "residualRisk" not in closure:
        return [{"id": "closure-complete", "detail": "outcome or residualRisk missing"}]
    if not contains_all(text, contract["requiredLedgerMarkers"][-3:]):
        return [{"id": "closure-complete", "detail": "validation markers incomplete"}]
    if not contains_all(text, contract["requiredClosureMarkers"]):
        return [{"id": "closure-complete", "detail": "closure markers incomplete"}]
    return []


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


def check_no_hardcoding(root: Path, contract: dict, errors: list[str]):
    terms = [term.lower() for term in contract["prohibited_candidate_terms"]]
    for rel_path in contract["expected_metadata"]["allowed_change_surface"]:
        text = (root / rel_path).read_text(encoding="utf-8", errors="replace").lower()
        for term in terms:
            if term in text:
                errors.append(f"Candidate file {rel_path} contains prohibited literal: {term}")


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list[str] = []

    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "toolchain-staging-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        failures = evaluate_invariants(root)
        failures.extend(evaluate_ledger(root, contract))
        failures.extend(evaluate_closure(root, contract))
        failure_ids = sorted(failure["id"] for failure in failures)
        if args.expect_start_state:
            expected = sorted(contract["expected_start_state_failures"])
            require(failure_ids == expected, f"Expected start-state failures {expected}, found {failure_ids}", errors)
        else:
            run_direct_tests(root, errors)
            check_no_hardcoding(root, contract, errors)
            if failures:
                rendered = json.dumps(failures, indent=2, sort_keys=True)
                errors.append(f"Completed candidate still fails staging invariants: {rendered}")

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
    print(f"N39 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
