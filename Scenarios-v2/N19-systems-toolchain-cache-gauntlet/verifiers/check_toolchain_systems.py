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
    parser = argparse.ArgumentParser(description="Check the N19 systems/toolchain gauntlet.")
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


def import_toolgate(root: Path):
    src_root = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src_root))
    for name in list(sys.modules):
        if name == "toolgate" or name.startswith("toolgate."):
            del sys.modules[name]
    return importlib.import_module("toolgate")


def cfg():
    return {
        "activeProfile": "linux-release",
        "legacyProfile": "windows-debug",
        "profiles": {
            "linux-release": {"build_root": "out/linux", "toolchain": "clang-18"},
            "windows-debug": {"build_root": "out/windows", "toolchain": "msvc-legacy"},
            "default": {"build_root": "out/default", "toolchain": "default-tool"},
        },
    }


def request(api, target, **kwargs):
    return api.BuildRequest(
        target=target,
        profile=kwargs.pop("profile", "linux-release"),
        source_hash=kwargs.pop("source_hash", f"hash-{target}"),
        features=tuple(kwargs.pop("features", ())),
        depends_on=tuple(kwargs.pop("depends_on", ())),
        priority=kwargs.pop("priority", 0),
        source=kwargs.pop("source", f"ticket-{target}"),
        workspace=kwargs.pop("workspace", "/workspace"),
    )


def assert_equal(actual, expected, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def evaluate_invariants(root: Path):
    api = import_toolgate(root)
    failures = []

    def case(case_id, fn):
        try:
            fn(api)
        except Exception as exc:  # noqa: BLE001 - verifier reports candidate behavior
            failures.append({"id": case_id, "detail": str(exc)})

    def active_profile_precedence(api):
        state = api.BuildState()
        events = api.run_toolchain(state, cfg(), [request(api, "base", source_hash="same")])
        assert_equal(events[0]["build_root"], "out/linux", "active profile build root")
        if "clang-18" not in events[0]["cache_key"]:
            raise AssertionError(f"active profile toolchain missing from cache key: {events[0]['cache_key']}")
        if "msvc-legacy" in events[0]["cache_key"]:
            raise AssertionError(f"legacy toolchain leaked into cache key: {events[0]['cache_key']}")

    def valid_env_override(api):
        state = api.BuildState()
        events = api.run_toolchain(
            state,
            cfg(),
            [request(api, "base", source_hash="same")],
            env={"BUILDGATE_BUILD_ROOT": "R:\\toolcache\\builds\\"},
        )
        assert_equal(events[0]["build_root"], "R:/toolcache/builds", "valid env root")

    def invalid_env_fallback(api):
        state = api.BuildState()
        events = api.run_toolchain(
            state,
            cfg(),
            [request(api, "base", source_hash="same")],
            env={"BUILDGATE_BUILD_ROOT": "relative/cache"},
        )
        assert_equal(events[0]["build_root"], "out/linux", "invalid env fallback")

    def dependency_order(api):
        state = api.BuildState()
        requests = [
            request(api, "child-linux", depends_on=("base-linux",), priority=50, source="ticket-child"),
            request(api, "base-linux", priority=1, source="ticket-base"),
        ]
        api.run_toolchain(state, cfg(), requests)
        assert_equal([event["target"] for event in state.ledger if event["type"] == "built"], ["base-linux", "child-linux"], "dependency order")

    def cache_key_portable(api):
        state = api.BuildState()
        left = request(api, "portable", source_hash="h", features=("zlib", "ssl"), workspace="C:/tmp/work-a")
        right = request(api, "portable", source_hash="h", features=("ssl", "zlib"), workspace="/var/tmp/work-b")
        api.run_toolchain(state, cfg(), [left, right])
        keys = [event["cache_key"] for event in state.ledger]
        assert_equal(len(set(keys)), 1, "portable cache key equality")
        bad_fragments = ["C:/tmp", "/var/tmp", "work-a", "work-b"]
        leaked = [fragment for fragment in bad_fragments if fragment in keys[0]]
        if leaked:
            raise AssertionError(f"workspace path leaked into cache key: {leaked}")

    def feature_conflict_rejected(api):
        state = api.BuildState()
        try:
            api.run_toolchain(state, cfg(), [request(api, "bad", features=("asan", "release-fast"))])
        except ValueError:
            return
        raise AssertionError("asan/release-fast conflict was not rejected")

    def lock_release_on_failure(api):
        state = api.BuildState()
        try:
            api.run_toolchain(state, cfg(), [request(api, "base")], fail_target="base")
        except RuntimeError:
            pass
        assert_equal(state.active_locks, set(), "active locks after failure")
        assert_equal([event["type"] for event in state.ledger], ["failed"], "failure ledger")

    def cache_hit_preserves_source(api):
        state = api.BuildState()
        first = request(api, "cacheable", source_hash="h-cache", source="ticket-cache")
        api.run_toolchain(state, cfg(), [first])
        second = request(api, "cacheable", source_hash="h-cache", source="ticket-cache-rerun")
        api.run_toolchain(state, cfg(), [second])
        assert_equal([event["type"] for event in state.ledger], ["built", "cache-hit"], "cache hit event")
        assert_equal([event["source"] for event in state.ledger], ["ticket-cache", "ticket-cache-rerun"], "cache source trace")

    def source_trace_report(api):
        state = api.BuildState()
        api.run_toolchain(state, cfg(), [request(api, "base", source="ticket-base")])
        summary = api.summarize_state(state)
        assert_equal(summary["sources"], ["ticket-base"], "report source trace")

    case("active-profile-precedence", active_profile_precedence)
    case("valid-env-override", valid_env_override)
    case("invalid-env-fallback", invalid_env_fallback)
    case("dependency-order", dependency_order)
    case("cache-key-portable", cache_key_portable)
    case("feature-conflict-rejected", feature_conflict_rejected)
    case("lock-release-on-failure", lock_release_on_failure)
    case("cache-hit-source-trace", cache_hit_preserves_source)
    case("source-trace-report", source_trace_report)
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


def check_no_hardcoding(root: Path, contract: dict, errors: list[str]):
    terms = [term.lower() for term in contract["prohibited_candidate_terms"]]
    for rel_path in contract["expected_metadata"]["allowed_change_surface"]:
        text = (root / rel_path).read_text(encoding="utf-8", errors="replace").lower()
        for term in terms:
            if term.lower() in text:
                errors.append(f"Candidate file {rel_path} contains prohibited literal: {term}")


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list[str] = []

    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "toolchain-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        failures = evaluate_invariants(root)
        failure_ids = sorted(failure["id"] for failure in failures)
        if args.expect_start_state:
            expected = sorted(contract["expected_start_state_failures"])
            require(failure_ids == expected, f"Expected start-state failures {expected}, found {failure_ids}", errors)
        else:
            run_direct_tests(root, errors)
            check_no_hardcoding(root, contract, errors)
            if failures:
                rendered = json.dumps(failures, indent=2, sort_keys=True)
                errors.append(f"Completed candidate still fails toolchain invariants: {rendered}")

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
    print(f"N19 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
