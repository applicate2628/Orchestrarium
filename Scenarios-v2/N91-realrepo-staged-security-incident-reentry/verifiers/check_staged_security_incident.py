#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import fnmatch
import hashlib
import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


sys.dont_write_bytecode = True

CONTRACT_ID = "N91-realrepo-staged-security-incident-reentry"

PROTECTED_SHA256 = {
    "candidate/README.md": "c20d0547d6cff1e8fb597417d2f6d995d50649974968ee6fd4b742620db0fafe",
    "candidate/workspace/README.md": "5e65bed54c173b2a1057ce39c1c676ec0b05c26882cc3e624b6ecdb53cbaf623",
    "candidate/workspace/src/incidentflow/__init__.py": "7dce3e8f3677956188cdbcd6b85d9eb8e38f9fd37c2726cd27c0a5e9b3725d0b",
    "candidate/workspace/src/incidentflow/models.py": "86a065d3c08d76e5a7b63a93fb5a77159cd95073b48b8eb4800e8e087e4bd03e",
    "candidate/workspace/src/incidentflow/service.py": "f58579c434fc9ed6d6422f2e4821f68528606af7d2a416d9367c1cc6882f8549",
    "candidate/workspace/tests/test_visible_flow.py": "5f596f7ac3ac2ee2e013c9f6c6cdfb4769d852c94fb71c5123477fb9cf2a9078",
}

EXPECTED_SOURCE_IDS = [f"S{index}" for index in range(1, 13)]
EXPECTED_PHASE_IDS = ["01-incident-ledger", "02-implementation", "03-exploit-validation", "04-closeout"]


def parse_args():
    parser = argparse.ArgumentParser(description="Verify the N91 staged security incident repair bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    parser.add_argument("--metrics-out", type=Path)
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key = None
    for raw_line in read_text(path).splitlines():
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
    for raw_line in read_text(path).splitlines():
        line = raw_line.rstrip()
        if line and not line.startswith(" ") and not line.startswith("#") and ":" in line:
            keys.append(line.split(":", 1)[0].strip())
    return keys


def require(condition: bool, message: str, errors: list[tuple[str, str]], failure_id: str):
    if not condition:
        errors.append((failure_id, message))


def normalize_path(path: str) -> str:
    return str(path).replace("\\", "/").strip("/")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_protected_hashes(root: Path, failures: list[tuple[str, str]]):
    for relative_path, expected in PROTECTED_SHA256.items():
        path = root / relative_path
        require(path.exists(), f"missing protected file {relative_path}", failures, "protected-file")
        if path.exists():
            require(sha256_file(path) == expected, f"protected file changed: {relative_path}", failures, "protected-file")


def check_shape(root: Path, contract: dict, failures: list[tuple[str, str]]):
    actual_entries = sorted(path.name for path in root.iterdir())
    require(
        actual_entries == sorted(contract["required_top_level_entries"]),
        f"top-level entries drifted: {actual_entries}",
        failures,
        "bundle-shape",
    )
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", failures, "scenario-yaml")
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", failures, "scenario-yaml")
    for relative_path in contract["required_bundle_paths"]:
        require((root / relative_path).exists(), f"missing required path {relative_path}", failures, "bundle-shape")
    check_protected_hashes(root, failures)


def check_changed_paths(contract: dict, changed_paths: list[str], failures: list[tuple[str, str]]):
    if not changed_paths:
        return
    actual = sorted(normalize_path(path) for path in changed_paths)
    expected = sorted(contract["requiredChangedPaths"])
    require(actual == expected, f"changed paths {actual} != required {expected}", failures, "scope-changed-paths")
    for path in actual:
        for pattern in contract["expected_metadata"]["must_not_touch"]:
            require(not fnmatch.fnmatch(path, pattern), f"changed protected path {path} matches {pattern}", failures, "scope-protected-path")


def import_workspace(root: Path):
    src = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src))
    for name in list(sys.modules):
        if name == "incidentflow" or name.startswith("incidentflow."):
            del sys.modules[name]
    return importlib.import_module("incidentflow")


def run_visible_tests(root: Path, failures: list[tuple[str, str]]):
    workspace = root / "candidate" / "workspace"
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=workspace,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    require(completed.returncode == 0, completed.stdout.strip(), failures, "visible-tests")


def b64_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode((text + "=" * (-len(text) % 4)).encode("ascii"))


def b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def tamper_token(token: str, field: str, value: Any) -> str:
    parts = token.split(".")
    if len(parts) == 3:
        header, payload, signature = parts
        data = json.loads(b64_decode(payload).decode("utf-8"))
        data[field] = value
        return ".".join([header, b64_encode(json.dumps(data, sort_keys=True).encode("utf-8")), signature])
    data = json.loads(b64_decode(token).decode("utf-8"))
    data[field] = value
    return b64_encode(json.dumps(data, sort_keys=True).encode("utf-8"))


def allowed(result: Any) -> bool:
    if isinstance(result, dict):
        return bool(result.get("allowed"))
    return bool(getattr(result, "allowed", False))


def denied_or_exception(fn) -> bool:
    try:
        result = fn()
    except Exception:  # noqa: BLE001 - denial by exception is acceptable for invalid token probes
        return True
    if result is None:
        return True
    if isinstance(result, dict):
        return result.get("allowed") is False or result.get("valid") is False or result.get("error") is not None
    return getattr(result, "allowed", True) is False or getattr(result, "valid", True) is False


def sample_accounts():
    return {
        "resource-hidden-a": {"tenant_id": "tenant-hidden-a", "owner_user_id": "user-hidden-a"},
        "resource-hidden-b": {"tenant_id": "tenant-hidden-b", "owner_user_id": "user-hidden-b"},
    }


def make_request(pkg, **overrides):
    data = {
        "tenant_id": "tenant-hidden-a",
        "user_id": "user-hidden-a",
        "resource_id": "resource-hidden-a",
        "role": "owner",
        "return_url": "https://exports.example.com/downloads/report.csv",
        "issued_at": 1_700_000_000,
        "nonce": "nonce-hidden-a",
        "break_glass_ticket": "",
    }
    data.update(overrides)
    return pkg.ExportRequest(**data)


def verify_runtime(root: Path, contract: dict, failures: list[tuple[str, str]]) -> float | None:
    try:
        pkg = import_workspace(root)
    except Exception as exc:  # noqa: BLE001
        failures.append(("import-workspace", f"cannot import incidentflow: {exc}"))
        return None

    try:
        service = pkg.ExportService(sample_accounts(), b"hidden-secret-material", ttl_seconds=90)
        started = time.perf_counter()
        valid = service.create_export(make_request(pkg), now=1_700_000_010)
        runtime = time.perf_counter() - started
        require(valid.get("allowed") is True, f"valid owner export denied: {valid!r}", failures, "runtime-valid-owner")
        token = valid.get("token")
        require(isinstance(token, str) and token, "valid export did not return token", failures, "runtime-valid-owner")

        cross_tenant = service.create_export(
            make_request(
                pkg,
                tenant_id="tenant-hidden-b",
                user_id="user-hidden-support",
                role="support",
                break_glass_ticket="BG-2026-incident",
            ),
            now=1_700_000_010,
        )
        require(cross_tenant.get("allowed") is False, f"cross-tenant support allowed: {cross_tenant!r}", failures, "runtime-tenant-boundary")

        support_no_ticket = service.create_export(
            make_request(pkg, user_id="support-user", role="support"),
            now=1_700_000_010,
        )
        require(support_no_ticket.get("allowed") is False, f"support without break-glass allowed: {support_no_ticket!r}", failures, "runtime-support-breakglass")

        support_ok = service.create_export(
            make_request(pkg, user_id="support-user", role="support", break_glass_ticket="BG-2026-incident"),
            now=1_700_000_010,
        )
        require(support_ok.get("allowed") is True, f"same-tenant support with break-glass denied: {support_ok!r}", failures, "runtime-support-breakglass")

        owner_mismatch = service.create_export(make_request(pkg, user_id="user-hidden-other"), now=1_700_000_010)
        require(owner_mismatch.get("allowed") is False, f"owner mismatch allowed: {owner_mismatch!r}", failures, "runtime-owner-binding")

        admin_ok = service.create_export(make_request(pkg, role="admin", user_id="admin-hidden-a"), now=1_700_000_010)
        require(admin_ok.get("allowed") is True, f"same-tenant admin denied: {admin_ok!r}", failures, "runtime-admin")

        if isinstance(token, str) and token:
            first_consume = service.consume_token(
                token,
                expected_tenant="tenant-hidden-a",
                expected_user="user-hidden-a",
                expected_resource="resource-hidden-a",
                now=1_700_000_010,
            )
            require(isinstance(first_consume, dict), f"token consume must return payload dict: {first_consume!r}", failures, "runtime-token-payload")
            require(
                denied_or_exception(
                    lambda: service.consume_token(
                        token,
                        expected_tenant="tenant-hidden-a",
                        expected_user="user-hidden-a",
                        expected_resource="resource-hidden-a",
                        now=1_700_000_011,
                    )
                ),
                "token replay was accepted",
                failures,
                "runtime-replay",
            )
            for field, value, failure_id in [
                ("tenant_id", "tenant-hidden-b", "runtime-token-tamper"),
                ("user_id", "user-hidden-b", "runtime-user-binding"),
                ("resource_id", "resource-hidden-b", "runtime-resource-binding"),
            ]:
                require(
                    denied_or_exception(
                        lambda field=field, value=value: service.consume_token(
                            tamper_token(token, field, value),
                            expected_tenant="tenant-hidden-a",
                            expected_user="user-hidden-a",
                            expected_resource="resource-hidden-a",
                            now=1_700_000_010,
                        )
                    ),
                    f"{field} tamper accepted",
                    failures,
                    failure_id,
                )

            expired_service = pkg.ExportService(sample_accounts(), b"hidden-secret-material", ttl_seconds=90)
            expired = expired_service.create_export(make_request(pkg, nonce="nonce-hidden-expiry"), now=1_700_000_010)
            expired_token = expired.get("token")
            require(
                denied_or_exception(
                    lambda: expired_service.consume_token(
                        expired_token,
                        expected_tenant="tenant-hidden-a",
                        expected_user="user-hidden-a",
                        expected_resource="resource-hidden-a",
                        now=1_700_000_200,
                    )
                ),
                "expired token was accepted",
                failures,
                "runtime-expiry",
            )

        redirect_cases = [
            "https://exports.example.com.evil.test/downloads/report.csv",
            "https://exports.example.com@evil.test/downloads/report.csv",
            "http://exports.example.com/downloads/report.csv",
            "https://exports.example.com/%2fdownloads/report.csv",
            "//exports.example.com/downloads/report.csv",
        ]
        for url in redirect_cases:
            observed = service.create_export(make_request(pkg, return_url=url, nonce=f"nonce-{hash(url)}"), now=1_700_000_010)
            require(observed.get("return_url") == contract["defaultReturnUrl"], f"redirect trap accepted: {url!r} -> {observed.get('return_url')!r}", failures, "runtime-redirect")

        safe_nested = "https://exports.example.com/downloads/2026/report.csv"
        safe_observed = service.create_export(make_request(pkg, return_url=safe_nested, nonce="nonce-safe-nested"), now=1_700_000_010)
        require(safe_observed.get("return_url") == safe_nested, f"safe nested return URL rejected: {safe_observed!r}", failures, "runtime-redirect-safe")

        audit_text = json.dumps(valid.get("audit", {}), sort_keys=True).lower()
        for forbidden in [str(token).lower(), "hidden-secret-material", "signature"]:
            require(forbidden not in audit_text, f"audit leaked {forbidden}", failures, "runtime-audit-redaction")
        require("fingerprint" in audit_text, "audit record missing fingerprint", failures, "runtime-audit-fingerprint")

        require(runtime <= float(contract["runtimeMaxSeconds"]), f"runtime {runtime:.3f}s exceeds budget", failures, "runtime-budget")
        return runtime
    except Exception as exc:  # noqa: BLE001
        failures.append(("runtime-exception", f"{type(exc).__name__}: {exc}"))
        return None


def json_text(value) -> str:
    return json.dumps(value, sort_keys=True)


def source_ids_present(value) -> set[str]:
    text = json_text(value)
    return {source_id for source_id in EXPECTED_SOURCE_IDS if source_id in text}


def find_phase(payload: dict, phase_id: str):
    for item in payload.get("phases", []):
        if not isinstance(item, dict):
            continue
        if item.get("id") == phase_id or item.get("phase") == phase_id or item.get("phaseId") == phase_id:
            return item
    return None


def require_terms(payload: Any, terms: list[str], label: str, failures: list[tuple[str, str]]):
    text = json_text(payload).lower()
    for term in terms:
        require(term.lower() in text, f"{label} missing term {term!r}", failures, f"{label}-terms")


def check_incident_ledger(root: Path, contract: dict, failures: list[tuple[str, str]]):
    try:
        payload = load_json(root / "candidate" / "incident-ledger.json")
    except Exception as exc:  # noqa: BLE001
        failures.append(("incident-ledger-json", str(exc)))
        return
    require(payload.get("contractId") == CONTRACT_ID, "incident-ledger contractId mismatch", failures, "incident-ledger-contract")
    missing_sources = sorted(set(EXPECTED_SOURCE_IDS) - source_ids_present(payload))
    require(not missing_sources, f"incident-ledger missing source IDs {missing_sources}", failures, "incident-ledger-source")
    for phase_id in EXPECTED_PHASE_IDS:
        phase = find_phase(payload, phase_id)
        require(phase is not None, f"incident-ledger missing phase {phase_id}", failures, "incident-ledger-phase")
        if phase:
            require(phase.get("owner") or phase.get("ownerPath"), f"phase {phase_id} missing owner", failures, "incident-ledger-phase")
    require_terms(payload, contract["incidentLedgerTerms"], "incident-ledger", failures)


def check_json_artifact(root: Path, rel: str, terms_key: str, contract: dict, failures: list[tuple[str, str]], *, changed_files=False):
    try:
        payload = load_json(root / rel)
    except Exception as exc:  # noqa: BLE001
        failures.append((f"{rel}-json", str(exc)))
        return
    require(payload.get("contractId") == CONTRACT_ID, f"{rel} contractId mismatch", failures, f"{rel}-contract")
    if changed_files:
        files = payload.get("changedFiles") or payload.get("changedPaths")
        require(sorted(normalize_path(path) for path in files or []) == sorted(contract["requiredChangedPaths"]), f"{rel} changed paths mismatch", failures, f"{rel}-changed-paths")
    require_terms(payload, contract[terms_key], rel, failures)


def check_ledgers(root: Path, contract: dict, failures: list[tuple[str, str]]):
    check_incident_ledger(root, contract, failures)
    check_json_artifact(root, "candidate/repair-ledger.json", "repairLedgerTerms", contract, failures, changed_files=True)
    check_json_artifact(root, "candidate/exploit-validation.json", "validationTerms", contract, failures)
    check_json_artifact(root, "candidate/reentry-state.json", "reentryTerms", contract, failures)
    check_json_artifact(root, "candidate/closeout.json", "closeoutTerms", contract, failures, changed_files=True)


def check_static_and_tests(root: Path, contract: dict, failures: list[tuple[str, str]]):
    code_paths = [
        root / "candidate/workspace/src/incidentflow/export_access.py",
        root / "candidate/workspace/src/incidentflow/download_tokens.py",
        root / "candidate/workspace/src/incidentflow/redirects.py",
        root / "candidate/workspace/src/incidentflow/audit.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in code_paths).lower()
    for term in contract["forbiddenStaticTerms"]:
        require(term.lower() not in combined, f"forbidden static term {term!r}", failures, "static-forbidden-term")
    for term in ["hmac", "sha256", "compare_digest", "urlparse"]:
        require(term in combined, f"implementation missing required primitive {term!r}", failures, "static-required-term")

    test_text = (root / "candidate/workspace/tests/test_incident_regression.py").read_text(encoding="utf-8", errors="replace")
    test_lower = test_text.lower()
    for term in contract["testRequiredTerms"]:
        require(term.lower() in test_lower, f"incident regression test missing {term!r}", failures, "test-required-term")
    assertion_count = test_lower.count("assert")
    require(assertion_count >= 10, f"incident regression test has only {assertion_count} assertions", failures, "test-assertions")


def write_metrics(path: Path | None, failures: list[tuple[str, str]], runtime: float | None):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    score = 100.0 if not failures else max(0.0, 100.0 - 4.0 * len(failures))
    path.write_text(
        json.dumps(
            {
                "verdict": "PASS" if not failures else "FAIL",
                "score": score,
                "errorCount": len(failures),
                "failureIds": [failure_id for failure_id, _ in failures],
                "runtimeSeconds": round(runtime, 6) if runtime is not None else None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "security-incident-contract.json")
    failures: list[tuple[str, str]] = []
    check_shape(root, contract, failures)

    if args.bundle_shape_only:
        write_metrics(args.metrics_out, failures, None)
        if failures:
            for failure_id, detail in failures:
                print(f"ERROR: {failure_id}: {detail}", file=sys.stderr)
            return 1
        print("N91 verifier PASS (bundle shape)")
        return 0

    check_changed_paths(contract, args.changed_paths, failures)
    run_visible_tests(root, failures)
    runtime = verify_runtime(root, contract, failures)
    check_static_and_tests(root, contract, failures)
    check_ledgers(root, contract, failures)

    if args.expect_start_state:
        observed = {failure_id for failure_id, _ in failures}
        expected = {
            "runtime-tenant-boundary",
            "runtime-support-breakglass",
            "runtime-owner-binding",
            "runtime-token-tamper",
            "runtime-replay",
            "runtime-redirect",
            "runtime-audit-redaction",
            "static-required-term",
            "test-required-term",
            "incident-ledger-source",
            "candidate/repair-ledger.json-changed-paths",
        }
        write_metrics(args.metrics_out, failures, runtime)
        if expected & observed:
            print("N91 verifier PASS (expected start-state failures present)")
            return 0
        print(f"ERROR: expected start-state failures missing; observed {sorted(observed)}", file=sys.stderr)
        return 1

    write_metrics(args.metrics_out, failures, runtime)
    if failures:
        for failure_id, detail in failures:
            print(f"Failed invariant: {failure_id} :: {detail}", file=sys.stderr)
        return 1

    print("N91 verifier PASS (100.0 / 100)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
