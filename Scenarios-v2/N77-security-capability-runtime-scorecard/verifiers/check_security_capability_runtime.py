#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import fnmatch
import importlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


CONTRACT_ID = "N77-W55-security-capability-runtime"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify N77 security capability runtime patch.")
    parser.add_argument("--bundle-root", type=Path, default=Path.cwd())
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--metrics-out", type=Path)
    parser.add_argument("--changed-path", action="append", default=[])
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in read_text(path).splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_key is None:
                raise AssertionError(f"list item without key in {path}: {line}")
            result.setdefault(current_key, []).append(line[4:].strip())
            continue
        if ":" not in line:
            raise AssertionError(f"cannot parse scenario yaml line: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        result[key] = [] if value == "" else value
    return result


def assert_bundle_shape(root: Path, failures: list[tuple[str, str]]) -> dict[str, Any]:
    contract_path = root / "oracle" / "security-capability-contract.json"
    if not contract_path.exists():
        failures.append(("bundle-contract", "missing oracle/security-capability-contract.json"))
        return {}
    contract = load_json(contract_path)
    for entry in contract["required_top_level_entries"]:
        if not (root / entry).exists():
            failures.append(("bundle-entry", f"missing top-level entry {entry}"))
    for rel in contract["required_bundle_paths"]:
        if not (root / rel).exists():
            failures.append(("bundle-path", f"missing required path {rel}"))

    scenario = parse_simple_yaml(root / "scenario.yaml")
    for field in contract["scenario_yaml_fields"]:
        if field not in scenario:
            failures.append(("scenario-field", f"missing scenario.yaml field {field}"))
    for key, expected in contract["expected_metadata"].items():
        if scenario.get(key) != expected:
            failures.append(("scenario-metadata", f"{key} mismatch: {scenario.get(key)!r} != {expected!r}"))
    return contract


def import_workspace(root: Path):
    src = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src))
    for name in list(sys.modules):
        if name == "capvault" or name.startswith("capvault."):
            del sys.modules[name]
    return importlib.import_module("capvault")


def run_visible_tests(root: Path, failures: list[tuple[str, str]]) -> None:
    workspace = root / "candidate" / "workspace"
    code = (
        "import os,sys,subprocess; "
        "os.environ['PYTHONPATH']='src'; "
        "raise SystemExit(subprocess.call([sys.executable,'-m','unittest','discover','-s','tests'], "
        f"cwd=r'{workspace}', env=os.environ.copy()))"
    )
    completed = subprocess.run([sys.executable, "-c", code], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode != 0:
        failures.append(("tests-visible", completed.stdout.strip()))


def _b64_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode((text + "=" * (-len(text) % 4)).encode("ascii"))


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def tamper_token(token: str, field: str, value: Any) -> str:
    parts = token.split(".")
    if len(parts) == 3:
        header, payload, signature = parts
        data = json.loads(_b64_decode(payload).decode("utf-8"))
        data[field] = value
        return ".".join([header, _b64_encode(json.dumps(data, sort_keys=True).encode("utf-8")), signature])
    data = json.loads(_b64_decode(token).decode("utf-8"))
    data[field] = value
    return _b64_encode(json.dumps(data, sort_keys=True).encode("utf-8"))


def alg_none_token(token: str) -> str:
    parts = token.split(".")
    payload = parts[1] if len(parts) == 3 else _b64_encode(_b64_decode(token))
    header = _b64_encode(json.dumps({"alg": "none", "kid": "live"}, sort_keys=True).encode("utf-8"))
    return f"{header}.{payload}."


def assert_denied(decision: Any, label: str, failures: list[tuple[str, str]]) -> None:
    if getattr(decision, "allowed", None) is not False:
        failures.append((label, f"expected denial, got {decision!r}"))


def verify_runtime(root: Path, contract: dict[str, Any], failures: list[tuple[str, str]]) -> float | None:
    try:
        module = import_workspace(root)
    except Exception as exc:
        failures.append(("import", f"cannot import capvault: {exc}"))
        return None

    try:
        service = module.CapabilityService({"live": b"hidden-secret-material"}, default_kid="live", ttl_seconds=120)
        request = module.ExportRequest(
            tenant_id="tenant-hidden-a",
            user_id="user-hidden-a",
            resource_id="resource-hidden-a",
            redirect_url="https://files.example.com/downloads/export.csv",
            issued_at=1000,
            nonce="nonce-hidden-a",
        )

        started = time.perf_counter()
        token = service.issue(request)
        used: set[str] = set()
        allowed = service.authorize(
            token,
            expected_tenant="tenant-hidden-a",
            expected_user="user-hidden-a",
            expected_resource="resource-hidden-a",
            redirect_url=request.redirect_url,
            now=1010,
            used_nonces=used,
        )
        runtime = time.perf_counter() - started

        if not getattr(allowed, "allowed", False):
            failures.append(("runtime-valid-token", f"valid token denied: {allowed!r}"))
        if getattr(allowed, "redirect_url", "") != request.redirect_url:
            failures.append(("runtime-safe-redirect", f"safe redirect changed: {allowed!r}"))
        if request.nonce not in used:
            failures.append(("runtime-nonce-consume", "valid nonce was not consumed"))

        replay = service.authorize(
            token,
            expected_tenant="tenant-hidden-a",
            expected_user="user-hidden-a",
            expected_resource="resource-hidden-a",
            redirect_url=request.redirect_url,
            now=1011,
            used_nonces=used,
        )
        assert_denied(replay, "runtime-replay", failures)

        tampered = service.authorize(
            tamper_token(token, "tenant_id", "tenant-hidden-b"),
            expected_tenant="tenant-hidden-a",
            expected_user="user-hidden-a",
            expected_resource="resource-hidden-a",
            redirect_url=request.redirect_url,
            now=1010,
            used_nonces=set(),
        )
        assert_denied(tampered, "runtime-tamper", failures)

        none_alg = service.authorize(
            alg_none_token(token),
            expected_tenant="tenant-hidden-a",
            expected_user="user-hidden-a",
            expected_resource="resource-hidden-a",
            redirect_url=request.redirect_url,
            now=1010,
            used_nonces=set(),
        )
        assert_denied(none_alg, "runtime-alg-none", failures)

        cross_user = service.authorize(
            token,
            expected_tenant="tenant-hidden-a",
            expected_user="user-hidden-b",
            expected_resource="resource-hidden-a",
            redirect_url=request.redirect_url,
            now=1010,
            used_nonces=set(),
        )
        assert_denied(cross_user, "runtime-user-binding", failures)

        expired = service.authorize(
            token,
            expected_tenant="tenant-hidden-a",
            expected_user="user-hidden-a",
            expected_resource="resource-hidden-a",
            redirect_url=request.redirect_url,
            now=1121,
            used_nonces=set(),
        )
        assert_denied(expired, "runtime-expiry", failures)

        default_url = contract["defaultReturnUrl"]
        redirect_traps = [
            "https://files.example.com.evil.test/downloads/export.csv",
            "https://files.example.com@evil.test/downloads/export.csv",
            "https://files.example.com/%5cdownloads/export.csv",
            "https://files.example.com/downloads/export.csv%0d%0aLocation:%20https://evil.test",
            "//files.example.com/downloads/export.csv",
        ]
        for trap in redirect_traps:
            observed = module.sanitize_return_url(trap)
            if observed != default_url:
                failures.append(("runtime-redirect-trap", f"{trap!r} returned {observed!r}"))
        safe_nested = "https://files.example.com/downloads/reports/2026/export.csv"
        if module.sanitize_return_url(safe_nested) != safe_nested:
            failures.append(("runtime-redirect-safe-path", "nested safe download path was rejected"))

        audit = module.audit_decision(allowed, token, "live")
        audit_text = json.dumps(audit, sort_keys=True).lower()
        if token.lower() in audit_text or "hidden-secret-material" in audit_text or "signature" in audit_text:
            failures.append(("runtime-audit-leak", "audit record leaked token, signature, or secret material"))
        if "fingerprint" not in audit_text:
            failures.append(("runtime-audit-fingerprint", "audit record does not include token fingerprint"))
        if runtime > float(contract["runtimeMaxSeconds"]):
            failures.append(("runtime-budget", f"runtime {runtime:.3f}s exceeds {contract['runtimeMaxSeconds']:.3f}s"))
        return runtime
    except Exception as exc:
        failures.append(("runtime-exception", f"{type(exc).__name__}: {exc}"))
        return None


def verify_changed_paths(contract: dict[str, Any], changed: list[str], failures: list[tuple[str, str]]) -> None:
    if not changed:
        return
    normalized = sorted(path.replace("\\", "/").strip("/") for path in changed)
    required = sorted(contract["requiredChangedPaths"])
    if normalized != required:
        failures.append(("scope-changed-paths", f"changed paths {normalized} != required {required}"))
    for path in normalized:
        for pattern in contract["expected_metadata"]["must_not_touch"]:
            if fnmatch.fnmatch(path, pattern):
                failures.append(("scope-protected-path", f"changed protected path {path} matches {pattern}"))


def verify_static_test_and_ledger(root: Path, contract: dict[str, Any], failures: list[tuple[str, str]]) -> None:
    code_paths = [
        root / "candidate" / "workspace" / "src" / "capvault" / "tokens.py",
        root / "candidate" / "workspace" / "src" / "capvault" / "redirects.py",
        root / "candidate" / "workspace" / "src" / "capvault" / "audit.py",
    ]
    combined = "\n".join(read_text(path) for path in code_paths).lower()
    for term in contract["forbiddenStaticTerms"]:
        if term.lower() in combined:
            failures.append(("static-forbidden-term", f"forbidden static term {term!r} present in implementation"))
    for term in ["hmac", "sha256", "compare_digest", "urlparse"]:
        if term not in combined:
            failures.append(("static-required-term", f"implementation does not reference {term!r}"))

    test_text = read_text(root / "candidate" / "workspace" / "tests" / "test_security_regression.py")
    test_lower = test_text.lower()
    for term in contract["testRequiredTerms"]:
        if term.lower() not in test_lower:
            failures.append(("test-required-term", f"security regression test missing {term!r}"))
    if test_lower.count("assert") < 6 and test_text.count("self.assert") < 4:
        failures.append(("test-assertions", "security regression test lacks enough assertions"))

    try:
        ledger = load_json(root / "candidate" / "security-ledger.json")
    except Exception as exc:
        failures.append(("ledger-json", f"cannot parse security-ledger.json: {exc}"))
        return
    if ledger.get("contractId") != CONTRACT_ID:
        failures.append(("ledger-contract", "contractId mismatch"))
    if sorted(ledger.get("changedFiles", [])) != sorted(contract["requiredChangedPaths"]):
        failures.append(("ledger-changed-files", "changedFiles must match required changed paths"))
    ledger_text = json.dumps(ledger, sort_keys=True).lower()
    for term in contract["ledgerRequiredTerms"]:
        if term.lower() not in ledger_text:
            failures.append(("ledger-term", f"missing {term!r}"))


def write_metrics(path: Path | None, failures: list[tuple[str, str]], runtime: float | None, contract: dict[str, Any]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "failure_ids": [item[0] for item in failures],
        "failures": [{"id": item[0], "detail": item[1]} for item in failures],
        "runtime_seconds": round(runtime, 6) if runtime is not None else None,
        "max_seconds": contract.get("runtimeMaxSeconds"),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = args.bundle_root.resolve()
    failures: list[tuple[str, str]] = []
    contract = assert_bundle_shape(root, failures)

    if args.bundle_shape_only:
        if failures:
            for _, detail in failures:
                print(detail)
            return 1
        print("N77 verifier PASS (bundle shape)")
        return 0

    runtime = None
    if not failures:
        verify_changed_paths(contract, args.changed_path, failures)
        run_visible_tests(root, failures)
        runtime = verify_runtime(root, contract, failures)
        verify_static_test_and_ledger(root, contract, failures)

    if args.expect_start_state:
        observed = {failure_id for failure_id, _ in failures}
        expected = {"runtime-tamper", "runtime-alg-none", "runtime-user-binding", "runtime-redirect-trap", "runtime-audit-leak", "static-required-term", "test-required-term", "ledger-contract"}
        write_metrics(args.metrics_out, failures, runtime, contract)
        if expected & observed:
            print("N77 verifier PASS (expected start-state failures present)")
            return 0
        print(f"N77 expected start-state failure missing; observed {sorted(observed)}")
        return 1

    write_metrics(args.metrics_out, failures, runtime, contract)
    if failures:
        for failure_id, detail in failures:
            print(f"Failed invariant: {failure_id} :: {detail}")
        return 1
    print("N77 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
