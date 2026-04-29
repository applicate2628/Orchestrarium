#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace


sys.dont_write_bytecode = True

FIXED_TIME = 1_712_188_800

PROTECTED_SHA256 = {
    "candidate/review-target/README.md": "fd7491ca20cdcc42d5d0eec288ab850c17b02162b8c9960991f9abe544580624",
    "candidate/review-target/security-depth/admin_api.py": "05a9ee90ae68d3b673ab7f791575ab1d5ad1269ec1dc13aed97ba152a1f2f072",
    "candidate/review-target/security-depth/session_tokens.py": "07a8461a2c5ffda0163fba60dce9e1e527e50e4c5014ecb97ed64e071433523a",
    "candidate/review-target/security-depth/webhook_handler.py": "b3f1f1fdcb53a2c23c05058034d95f8c2435e7c14b7011496dc826aa1013fc5f",
    "candidate/review-target/security-depth/audit_log.py": "a1db64084669a8aa55f65221b59e0298ffec2855b86b658d1e8a04515e0c96b2",
    "candidate/review-target/security-depth/export_links.py": "5ac63c532077700044c9e2599aec6d6edda2d2ebfdb51f1218494a01fb183b07",
    "candidate/review-target/security-depth/admin_console.html": "8ff98ebe9ac39450dd9a827a7f0d1a50509c7007075285843008777cfb59700d",
}

FINDING_TUPLE_DIGESTS = {
    "R1": ["e31ca793d0cf6b4e45136cbf184addfd053940505984916a3d476073b0237eeb"],
    "R2": [
        "2f2bfb0e95bf64d56fc41ba30957e94b3853259d78e3d6b8c918c250ba29572c",
        "55d8f40255daa1dc0cc9467124d6213961f3ed833414b50bc82526c2570fb991",
    ],
    "R3": [
        "95d5e1bca8deee4dc189208c85c7a7a9e14f540eeb3902a880f0a4e6ba780ea1",
        "1d878138a4be3852e1e19b8d386a02b7073a6013224c344d9b4071218fde8a34",
    ],
    "R4": [
        "a109a1cc7fe59c148b107e250c55f4b9d45f3f020274860f26de78757be5dbad",
        "ca595d2fca6e18eaf00617094529a4cac6a786310b7cfe3c1aba2c0414e0faf6",
    ],
    "R5": ["dd0a2c3960fb9eae41ea1479ea23d9a4f6ce415dead7a484575b89831028d477"],
    "R6": ["37461eec61af48df42bec251ae7358671be24d12e29e468795f1c6e977f440aa"],
    "R7": [
        "be6fcd8000115cd2121f6fd8a3ee2965ee5981a4c42661d3267e434df41b4dfc",
        "cb365c1737516e685c6fc84dc9d9a08bf08684af54b5d58940b5c0fb7eefc5b3",
    ],
    "R8": [
        "c14d400e30bc8b5f8baca4904c844223cfeeafd45a3e416d682f642023b78756",
        "0f122f21cd2c7b9d42b7d7d45df70f86a1392fb6d0ae7cc6ad3597325ee8a176",
        "266348e45e62cb7ae7919a3a869b5d7739c676c97b38e796b612da6c9841f6b4",
    ],
    "R9": ["e86520100f1525383cfe6c78403dcece5e6c2046299c803e402d6fc2640f0a52"],
}


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N89 security runtime-witness review bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--metrics-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


def text_has_all(value, terms):
    text = str(value or "").lower()
    return all(str(term).lower() in text for term in terms)


def sha256_file(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_target_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import target module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def identifiers_from_line(root: Path, relative_path: str, line_no: int):
    path = root / relative_path
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_no < 1 or line_no > len(lines):
        return []
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", lines[line_no - 1])


def containing_function(root: Path, relative_path: str, line_no: int):
    lines = (root / relative_path).read_text(encoding="utf-8").splitlines()
    current = "module"
    for index, line in enumerate(lines[:line_no], start=1):
        match = re.match(r"\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
        if match:
            current = match.group(1)
    return current


class Request:
    def __init__(self, *, json_body=None, args=None, headers=None, body=b"", auth=None, path="/admin"):
        self.json = json_body
        self.args = args or {}
        self.headers = headers or {}
        self.body = body
        self.auth = auth or SimpleNamespace(tenant_id="tenant-attacker", role="viewer", user_id="attacker-user")
        self.path = path


class Ledger:
    def __init__(self):
        self.calls = []

    def approve_transfer(self, tenant_id, transfer_id, *, approved_by):
        self.calls.append({"tenant_id": tenant_id, "transfer_id": transfer_id, "approved_by": approved_by})
        return {"status": "approved", "tenant_id": tenant_id, "transfer_id": transfer_id, "approved_by": approved_by}


class AccountExporter:
    def __init__(self):
        self.calls = []

    def export(self, tenant_id, *, include_hidden):
        rows = ["visible-account"]
        if include_hidden:
            rows.append("hidden-account")
        self.calls.append({"tenant_id": tenant_id, "include_hidden": include_hidden, "rows": rows})
        return {"tenant_id": tenant_id, "include_hidden": include_hidden, "rows": rows}


class Response:
    def __init__(self):
        self.cookies = []

    def set_cookie(self, name, value, **kwargs):
        self.cookies.append({"name": name, "value": value, **kwargs})


class EventStore:
    def __init__(self):
        self.records = []

    def record(self, event_id):
        self.records.append(event_id)


class Credits:
    def __init__(self):
        self.grants = []

    def grant(self, account_id, amount):
        self.grants.append({"account_id": account_id, "amount": amount})
        return {"status": "accepted", "account_id": account_id, "amount": amount}


class AuditSink:
    def __init__(self):
        self.entries = []

    def write(self, entry):
        self.entries.append(entry)


def compute_runtime_observations(root: Path):
    target = root / "candidate" / "review-target" / "security-depth"
    admin_api = import_target_module(target / "admin_api.py", "n89_admin_api")
    session_tokens = import_target_module(target / "session_tokens.py", "n89_session_tokens")
    webhook_handler = import_target_module(target / "webhook_handler.py", "n89_webhook_handler")
    audit_log = import_target_module(target / "audit_log.py", "n89_audit_log")
    export_links = import_target_module(target / "export_links.py", "n89_export_links")

    observations = {}

    ledger = Ledger()
    admin_api.ledger = ledger
    admin_api.account_exporter = AccountExporter()
    admin_api.approve_wire_transfer(
        Request(
            json_body={"tenant_id": "tenant-victim"},
            auth=SimpleNamespace(tenant_id="tenant-attacker", role="finance-admin", user_id="attacker-user"),
        ),
        "wire-700",
    )
    observations["R1"] = {"tenant_id": ledger.calls[-1]["tenant_id"], "transfer_id": "wire-700", "approved_by": "attacker-user"}

    ledger = Ledger()
    admin_api.ledger = ledger
    result = admin_api.approve_wire_transfer(Request(json_body={"acting_role": "finance-admin"}), "wire-701")
    observations["R2"] = {"acting_role": "finance-admin", "status": result["status"], "transfer_id": "wire-701"}

    exporter = AccountExporter()
    admin_api.account_exporter = exporter
    admin_api.export_accounts(Request(json_body={}, args={"include_hidden": "1"}))
    observations["R3"] = {"tenant_id": "tenant-attacker", "include_hidden": True, "rows": exporter.calls[-1]["rows"]}

    session_tokens.time = SimpleNamespace(time=lambda: FIXED_TIME)
    token = session_tokens.issue_reset_token(SimpleNamespace(id="usr-314", email="alice@example.com"))
    observations["R4"] = {"token": token, "bucket": FIXED_TIME // 300, "email_prefix": "alice"}

    response = Response()
    session_tokens.set_admin_cookie(response, "sess-abc")
    cookie = response.cookies[-1]
    observations["R5"] = {"cookie": cookie["name"], "httponly": cookie["httponly"], "secure": cookie["secure"], "samesite": cookie["samesite"]}

    event_store = EventStore()
    credits = Credits()
    webhook_handler.event_store = event_store
    webhook_handler.credits = credits
    body = json.dumps({"event_id": "event-pay-1", "account_id": "acct-77", "amount": 250}, separators=(",", ":")).encode("utf-8")
    result = webhook_handler.handle_billing_webhook(
        Request(args={"debug_signature": "skip"}, headers={"X-Billing-Signature": "bad"}, body=body),
        "billing-secret",
    )
    observations["R6"] = {"debug_signature": "skip", "status": result["status"], "account_id": "acct-77", "amount": 250}

    event_store = EventStore()
    credits = Credits()
    webhook_handler.event_store = event_store
    webhook_handler.credits = credits
    body = json.dumps({"event_id": "event-pay-2", "account_id": "acct-77", "amount": 250}, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(b"billing-secret", body, hashlib.sha256).hexdigest()
    req = Request(headers={"X-Billing-Signature": signature}, body=body)
    webhook_handler.handle_billing_webhook(req, "billing-secret")
    webhook_handler.handle_billing_webhook(req, "billing-secret")
    observations["R7"] = {"event_id": "event-pay-2", "record_count": len(event_store.records), "grant_count": len(credits.grants)}

    audit_sink = AuditSink()
    entry = audit_log.audit_admin_request(
        Request(
            json_body={"action": "view"},
            headers={"Authorization": "Bearer live-admin-token", "Cookie": "sid=admin-session"},
            path="/admin/export",
        ),
        audit_sink,
    )
    observations["R8"] = {"authorization": entry["authorization"], "cookie": entry["cookie"], "sink": "audit_sink.write"}

    url = export_links.build_download_url(SimpleNamespace(path="/q4.csv", owner_email="owner@example.com"))
    observations["R9"] = {"url": url, "api_key": "svc_live_export_key_from_env", "owner_email": "owner@example.com"}

    admin_source = (target / "admin_api.py").read_text(encoding="utf-8")
    console_source = (target / "admin_console.html").read_text(encoding="utf-8")
    health = admin_api.health()
    if "MASKED_EXAMPLE_TOKEN" not in admin_source or "audit_sink.write(MASKED_EXAMPLE_TOKEN)" in admin_source:
        raise RuntimeError("B1 source-only self-check failed")
    if 'rel="noopener"' not in console_source:
        raise RuntimeError("B2 noopener self-check failed")
    if health != {"ok": True}:
        raise RuntimeError("B3 health self-check failed")
    observations["B1"] = {"token": "MASKED_EXAMPLE_TOKEN", "source_only": True, "propagated_to_sink": False}
    observations["B2"] = {"rel": "noopener", "purpose": "link hardening", "vulnerability": False}
    observations["B3"] = {"endpoint": "GET /health", "response": health, "privileged_state": False}
    return observations


def check_protected_hashes(root: Path, errors: list[str]):
    for relative_path, expected in PROTECTED_SHA256.items():
        path = root / relative_path
        require(path.exists(), f"Protected file missing: {relative_path}", errors)
        if path.exists():
            require(sha256_file(path) == expected, f"Protected file changed: {relative_path}", errors)


def check_shape(root: Path, contract: dict, errors: list[str]):
    actual_entries = sorted(path.name for path in root.iterdir())
    require(actual_entries == sorted(contract["required_top_level_entries"]), f"Top-level bundle entries drifted: {actual_entries}", errors)
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", errors)
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", errors)
    for relative_path in contract["required_bundle_paths"]:
        require((root / relative_path).exists(), f"Missing required bundle path: {relative_path}", errors)
    check_protected_hashes(root, errors)
    observations = compute_runtime_observations(root)
    expected_cases = sorted(contract["required_exploit_case_ids"] + contract["required_benign_case_ids"])
    require(sorted(observations) == expected_cases, "Runtime witness case set mismatch", errors)


def check_changed_paths(changed_paths: list[str], contract: dict, errors: list[str]):
    allowed = set(contract["expected_metadata"]["allowed_change_surface"])
    unexpected = sorted(path for path in changed_paths if path not in allowed)
    if unexpected:
        errors.append("Changed path outside allowed surface: " + ", ".join(unexpected))


def finding_tuple_digest(finding: dict):
    repro = finding.get("reproduction") if isinstance(finding.get("reproduction"), dict) else {}
    return canonical_digest(
        {
            "caseId": repro.get("caseId"),
            "file": finding.get("file"),
            "line": finding.get("line"),
            "category": finding.get("category"),
            "severity": finding.get("severity"),
        }
    )


def check_source_evidence(root: Path, finding: dict, errors: list[str]):
    relative_path = finding.get("file")
    line = finding.get("line")
    if not isinstance(relative_path, str) or not isinstance(line, int):
        return
    identifiers = [token for token in identifiers_from_line(root, relative_path, line) if token not in {"def", "return", "if", "or", "in"}]
    if identifiers:
        require(any(token.lower() in str(finding.get("sourceEvidence", "")).lower() for token in identifiers), f"{finding.get('id')}: sourceEvidence is not bound to cited line", errors)


def check_findings(root: Path, report: dict, contract: dict, errors: list[str]):
    findings = report.get("findings")
    require(isinstance(findings, list), "findings must be a list", errors)
    if not isinstance(findings, list):
        return {}
    require(len(findings) == contract["exact_finding_count"], f"expected {contract['exact_finding_count']} findings, got {len(findings)}", errors)

    allowed_categories = set(contract["allowed_categories"])
    allowed_severities = set(contract["allowed_severities"])
    by_case = {}
    by_id = {}
    required_keys = ["category", "file", "fixBoundary", "id", "line", "reproduction", "severity", "sourceEvidence", "title"]
    for index, finding in enumerate(findings, start=1):
        require(isinstance(finding, dict), f"finding {index} must be an object", errors)
        if not isinstance(finding, dict):
            continue
        require(sorted(finding.keys()) == required_keys, f"finding {index}: keys mismatch", errors)
        fid = finding.get("id")
        require(isinstance(fid, str) and re.fullmatch(r"F[1-9]", fid or "") is not None, f"finding {index}: id must be F1..F9", errors)
        require(fid not in by_id, f"duplicate finding id: {fid}", errors)
        by_id[fid] = finding
        require(finding.get("category") in allowed_categories, f"{fid}: invalid category", errors)
        require(finding.get("severity") in allowed_severities, f"{fid}: invalid severity", errors)
        repro = finding.get("reproduction")
        require(isinstance(repro, dict), f"{fid}: reproduction must be an object", errors)
        if not isinstance(repro, dict):
            continue
        require(sorted(repro.keys()) == ["attackerAction", "caseId", "observedImpact", "violatedInvariant"], f"{fid}: reproduction keys mismatch", errors)
        case_id = repro.get("caseId")
        require(case_id in contract["required_exploit_case_ids"], f"{fid}: invalid reproduction.caseId", errors)
        require(case_id not in by_case, f"duplicate reproduction case: {case_id}", errors)
        by_case[case_id] = finding
        require(finding_tuple_digest(finding) in FINDING_TUPLE_DIGESTS.get(case_id, []), f"{fid}: exact finding tuple mismatch", errors)
        require(all(str(repro.get(key, "")).strip() for key in ("attackerAction", "observedImpact", "violatedInvariant")), f"{fid}: reproduction text must be non-empty", errors)
        require(str(finding.get("title", "")).strip(), f"{fid}: title must be non-empty", errors)
        require(str(finding.get("sourceEvidence", "")).strip(), f"{fid}: sourceEvidence must be non-empty", errors)
        require(str(finding.get("fixBoundary", "")).strip(), f"{fid}: fixBoundary must be non-empty", errors)
        check_source_evidence(root, finding, errors)

    missing_cases = sorted(set(contract["required_exploit_case_ids"]) - set(by_case))
    require(not missing_cases, "missing exploit cases: " + ", ".join(missing_cases), errors)
    return by_case


def check_false_positives(report: dict, contract: dict, errors: list[str]):
    items = report.get("falsePositiveAvoided")
    require(isinstance(items, list), "falsePositiveAvoided must be a list", errors)
    if not isinstance(items, list):
        return
    require(len(items) == contract["exact_false_positive_count"], f"falsePositiveAvoided expected {contract['exact_false_positive_count']} rows, got {len(items)}", errors)
    by_case = {item.get("caseId"): item for item in items if isinstance(item, dict)}
    require(len(by_case) == len(items), "falsePositiveAvoided case ids must be distinct", errors)
    expected = {
        "B1": (["MASKED_EXAMPLE_TOKEN", "sk_test_example"], ["synthetic", "sink"]),
        "B2": (["rel=\"noopener\""], ["hardening", "link"]),
        "B3": (["GET /health"], ["public", "privileged"]),
    }
    for case_id, (pattern_terms, reason_terms) in expected.items():
        item = by_case.get(case_id)
        require(item is not None, f"missing false-positive case {case_id}", errors)
        if item:
            require(sorted(item.keys()) == ["caseId", "pattern", "reason"], f"{case_id}: falsePositiveAvoided keys mismatch", errors)
            require(text_has_all(item.get("pattern"), pattern_terms), f"{case_id}: pattern missing terms", errors)
            require(text_has_all(item.get("reason"), reason_terms), f"{case_id}: reason missing terms", errors)


def expected_witness_status(case_id: str):
    return "benign" if case_id.startswith("B") else "reproduced"


def check_source_binding(root: Path, item: dict, finding: dict | None, case_id: str, errors: list[str]):
    binding = item.get("sourceBinding")
    require(isinstance(binding, dict), f"witness {case_id}: sourceBinding must be an object", errors)
    if not isinstance(binding, dict):
        return
    require(sorted(binding.keys()) == ["file", "function", "line", "sink"], f"witness {case_id}: sourceBinding keys mismatch", errors)
    if case_id.startswith("R"):
        require(finding is not None, f"witness {case_id}: no matching finding", errors)
        if finding is None:
            return
        require(binding.get("file") == finding.get("file"), f"witness {case_id}: sourceBinding.file mismatch", errors)
        require(binding.get("line") == finding.get("line"), f"witness {case_id}: sourceBinding.line mismatch", errors)
        expected_function = containing_function(root, finding["file"], finding["line"])
        require(binding.get("function") == expected_function, f"witness {case_id}: sourceBinding.function mismatch", errors)
        require(isinstance(binding.get("sink"), str) and binding["sink"].strip(), f"witness {case_id}: sourceBinding.sink must be non-empty", errors)
    else:
        require(binding.get("file", "").startswith("candidate/review-target/"), f"witness {case_id}: benign sourceBinding.file mismatch", errors)
        require(isinstance(binding.get("line"), int), f"witness {case_id}: benign sourceBinding.line must be an int", errors)
        require(isinstance(binding.get("function"), str) and binding["function"].strip(), f"witness {case_id}: benign sourceBinding.function must be non-empty", errors)


def check_witness_matrix(root: Path, report: dict, contract: dict, observations: dict, findings_by_case: dict, errors: list[str]):
    items = report.get("witnessMatrix")
    require(isinstance(items, list), "witnessMatrix must be a list", errors)
    if not isinstance(items, list):
        return
    require(len(items) == contract["exact_witness_count"], f"witnessMatrix expected {contract['exact_witness_count']} rows, got {len(items)}", errors)
    by_case = {item.get("caseId"): item for item in items if isinstance(item, dict)}
    require(len(by_case) == len(items), "witnessMatrix case ids must be distinct", errors)
    expected_cases = contract["required_exploit_case_ids"] + contract["required_benign_case_ids"]
    for case_id in expected_cases:
        item = by_case.get(case_id)
        require(item is not None, f"missing witness case {case_id}", errors)
        if not item:
            continue
        require(sorted(item.keys()) == ["caseId", "findingId", "observed", "sourceBinding", "status"], f"witness {case_id}: keys mismatch", errors)
        require(item.get("status") == expected_witness_status(case_id), f"witness {case_id}: status mismatch", errors)
        if case_id.startswith("R"):
            finding = findings_by_case.get(case_id)
            require(finding is not None and item.get("findingId") == finding.get("id"), f"witness {case_id}: findingId mismatch", errors)
        else:
            finding = None
            require(item.get("findingId") is None, f"witness {case_id}: benign findingId must be null", errors)
        require(item.get("observed") == observations.get(case_id), f"witness {case_id}: observed object mismatch", errors)
        check_source_binding(root, item, finding, case_id, errors)


def check_report(root: Path, contract: dict, observations: dict, errors: list[str]):
    report_path = root / contract["editable_report"]
    require(report_path.exists(), f"Missing candidate report: {contract['editable_report']}", errors)
    if not report_path.exists():
        return
    try:
        report = load_json(report_path)
    except Exception as exc:  # noqa: BLE001 - verifier reports candidate artifact
        errors.append(f"Report is not valid JSON: {exc}")
        return

    require(sorted(report.keys()) == sorted(contract["required_top_level_report_keys"]), f"Report top-level keys mismatch: {sorted(report.keys())}", errors)
    require(report.get("contractId") == contract["contractId"], "contractId mismatch", errors)
    require(report.get("gateDecision") == contract["expected_gate_decision"], "gateDecision mismatch", errors)
    raw_report = json.dumps(report, sort_keys=True)
    for snippet in contract["prohibited_report_snippets"]:
        require(snippet.lower() not in raw_report.lower(), f"Prohibited snippet present: {snippet}", errors)

    findings_by_case = check_findings(root, report, contract, errors)
    check_false_positives(report, contract, errors)
    check_witness_matrix(root, report, contract, observations, findings_by_case, errors)


def write_metrics(path: Path | None, errors: list[str], observations: dict):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    score = 100.0 if not errors else max(0.0, 100.0 - 5.0 * len(errors))
    path.write_text(
        json.dumps(
            {
                "score": score,
                "passed": not errors,
                "errorCount": len(errors),
                "witnessCases": sorted(observations),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "security-runtime-witness-contract.json")
    errors: list[str] = []
    observations: dict = {}

    try:
        check_shape(root, contract, errors)
        observations = compute_runtime_observations(root)
    except Exception as exc:  # noqa: BLE001 - verifier reports bundle drift
        errors.append(f"Runtime witness harness failed: {exc}")

    if args.changed_paths:
        check_changed_paths(args.changed_paths, contract, errors)
    if args.bundle_shape_only:
        write_metrics(args.metrics_out, errors, observations)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("N89 verifier PASS (bundle shape)")
        return 0

    check_report(root, contract, observations, errors)
    if args.expect_start_state:
        expected = {"expected 9 findings", "gateDecision mismatch", "witnessMatrix expected 12 rows"}
        observed = "\n".join(errors)
        missing = [needle for needle in expected if needle not in observed]
        if missing:
            print(f"ERROR: start state no longer exposes expected failures: {missing}", file=sys.stderr)
            return 1
        print("N89 verifier PASS (expected start-state failures present)")
        return 0

    write_metrics(args.metrics_out, errors, observations)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("N89 verifier PASS (100.0 / 100)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
