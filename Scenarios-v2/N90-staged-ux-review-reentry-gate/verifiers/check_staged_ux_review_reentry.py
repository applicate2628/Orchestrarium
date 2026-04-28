#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path


sys.dont_write_bytecode = True

PROTECTED_SHA256 = {
    "candidate/review-target/README.md": "9476a6e5c93d8dd9737bfe656abe2d1befede03c713e5cddbaf435b449f303d8",
    "candidate/review-target/ux_runtime/publish_state.py": "289a2721e6a00c7e59c1e7e56cd96c9d3b4124e076fd85d2519ce410eb41431d",
    "candidate/review-target/ux_runtime/rendering.py": "1dbd178b1e9409d25db9bd09c830556342bb07ab33d9d83546a56097d15a2d88",
    "candidate/review-target/ux_runtime/export_summary.py": "efdc9866a26332a6446373e55e68a1ddf18d52ef11648684ee69e7fabf4eec3c",
    "candidate/review-target/ux_runtime/reentry_flow.py": "d8449c4515f9eb7b4298a0541f47ef0f27e17a08a6cbe20037cb2798d367318b",
    "candidate/review-target/ux_runtime/publish_console.css": "1588e9ffc5fc74fd17e551ae6f6150ca537d8da4cbd209ca5f7a58f363f18e16",
    "candidate/review-target/docs/stale-ux-notes.md": "91a945f9fd3ab3dfd786010fa845a0c01389a8e6122b7a8f1884e80a31dda9ec",
}

FINDING_TUPLE_DIGESTS = {
    "R1": [
        "70cc26b404eb10fed5c0aa61429a8b33cd3000ba2d944a89af4f4429f5fb1016",
    ],
    "R2": [
        "3fe1aae3cfb528754b2dff0fdfa76903b5e3a1f2921da2105b456093821e188a",
    ],
    "R3": [
        "ef092c661d3da6a24cf54440141bb18eb1462a4a12f18135aef7b287de3bf2b3",
    ],
    "R4": [
        "4df3b4962ed66a06591c3496d33aae5bf9efe7fcbd4d52f30e8267285c42ee43",
    ],
    "R5": [
        "ca99c22b69d6734adbb7d48df3b99b1fe6de7d0362d4a0860a6431bbf69aa918",
        "466f1ec5ca76c54b1277ddbc2cff6ffae61e59053c0ae22bfd5cd859117cbdbd",
    ],
    "R6": [
        "3b1be1e00404273a12e78ea8ca72135927f6ec338f6502810faef9788e8bbbab",
        "5563375d2806b842f40719606615904303f3bbb056218f09426277c804258103",
    ],
    "R7": [
        "3e25b4aaad6279d29906c26f2cab7f1df719fa1e0f8f1df6f04f54bab3c5259f",
    ],
}

RESPONSE_DECISION_DIGESTS = {
    "A1-stale-source-advisory": "6ebdf98283fa5b017a9f081af177335ad6b5a07a7423b51edc277cda79abf745",
    "A2-regression-proof-required": "d331074a5594d61821eaecb8ddb4b8a1a3bf4107875a7a0fa1e59bc5e6c43ed8",
    "A3-owner-first-priority": "bb633d8923bf93b7976e42e214db546f854a93b048f8dcf8e4482774de169b99",
    "A4-mobile-disabled-publish-first": "72d4b28f55a081f6bb64d1de095f54c8499fc12e4bdaa21da8f86344b0217af4",
    "A5-redact-auditor-export": "c4d1b9ecdf0adb53b9602bc191f53fb2650e622561c8a00b091cc83a6914d15b",
    "A6-follow-up-reentry-block": "b2d84fe4b3c2d885cfee2fce851ae2040b904bfd74c61b5af199d4456c455a5f",
    "A7-disabled-opacity-bug": "cd6d0bf042d2ce8b6095267d064f22f3caf8830022a910683b14dedf973f0f5a",
}

EXPECTED_SOURCE_IDS = [f"S{index}" for index in range(1, 13)]
EXPECTED_PHASE_IDS = [
    "01-source-state-ledger",
    "02-decision-adr",
    "03-ux-findings",
    "04-response-closeout",
]
EXPECTED_RUNTIME_CASE_IDS = ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]
EXPECTED_BENIGN_CASE_IDS = ["B1", "B2", "B3"]
EXPECTED_EDITABLE_PATHS = [
    "candidate/ux-review-state.json",
    "candidate/decision-adr.md",
    "candidate/findings.json",
    "candidate/response-gate.json",
    "candidate/closure.json",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N90 staged UX review/reentry gate bundle.")
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


def sha256_file(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_target_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import target module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_path(value):
    return str(value).replace("\\", "/")


def json_text(value):
    return json.dumps(value, sort_keys=True)


def text_has_all(value, terms):
    text = str(value or "").lower()
    return all(str(term).lower() in text for term in terms)


def identifiers_from_line(root: Path, relative_path: str, line_no: int):
    path = root / relative_path
    lines = path.read_text(encoding="utf-8").splitlines()
    if line_no < 1 or line_no > len(lines):
        return []
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", lines[line_no - 1])


def containing_function(root: Path, relative_path: str, line_no: int):
    lines = (root / relative_path).read_text(encoding="utf-8").splitlines()
    current = "module"
    for line in lines[:line_no]:
        match = re.match(r"\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
        if match:
            current = match.group(1)
    return current


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
    require(sorted(observations) == sorted(EXPECTED_RUNTIME_CASE_IDS + EXPECTED_BENIGN_CASE_IDS), "Runtime case set mismatch", errors)


def check_changed_paths(changed_paths: list[str], errors: list[str]):
    if not changed_paths:
        return
    actual = sorted(normalize_path(path) for path in changed_paths)
    expected = sorted(EXPECTED_EDITABLE_PATHS)
    require(actual == expected, f"changed paths mismatch: expected {expected}, got {actual}", errors)


def compute_runtime_observations(root: Path):
    target = root / "candidate" / "review-target" / "ux_runtime"
    publish_state = import_target_module(target / "publish_state.py", "n90_publish_state")
    rendering = import_target_module(target / "rendering.py", "n90_rendering")
    export_summary = import_target_module(target / "export_summary.py", "n90_export_summary")
    reentry_flow = import_target_module(target / "reentry_flow.py", "n90_reentry_flow")

    observations = {}
    observations["R1"] = publish_state.derive_publish_state(
        {"owner_id": "owner-17", "regression_status": "passed", "source_status": "conflict"}
    )
    observations["R2"] = publish_state.derive_publish_state(
        {"owner_id": "owner-17", "regression_status": "pending", "source_status": "fresh"}
    )
    observations["R3"] = {
        "state": publish_state.derive_publish_state(
            {"owner_id": None, "regression_status": "passed", "source_status": "conflict", "due_minutes": 7}
        ),
        "queuePriority": list(
            publish_state.queue_priority_key(
                {"owner_id": None, "regression_status": "passed", "source_status": "conflict", "due_minutes": 7}
            )
        ),
    }
    observations["R4"] = {"mobileOrder": rendering.mobile_action_order({"publish_enabled": False})}
    observations["R5"] = export_summary.build_auditor_export(
        {
            "public_summary": "Ready except owner review",
            "visible_status": "draft",
            "owner_notes": "Owner-only escalation note",
            "internal_resolution": "internal rollback path",
        }
    )
    observations["R6"] = reentry_flow.after_follow_up_diff(
        {"publish_receipt_visible": True, "follow_up_blocked": True, "return_focus": "evidence-row-source"},
        {"kind": "text-only"},
    )
    observations["R7"] = reentry_flow.after_owner_added(
        {"publish_receipt_visible": False, "follow_up_blocked": True, "return_focus": "evidence-row-owner"}
    )

    css = (target / "publish_console.css").read_text(encoding="utf-8")
    docs_link = export_summary.docs_link()
    observations["B1"] = {
        "opacity": "opacity: 0.48" in css,
        "visibleDisabledReason": "attr(data-disabled-reason)" in css,
    }
    observations["B2"] = {"docsLink": docs_link, "noopener": 'rel="noopener"' in docs_link}
    observations["B3"] = {"emptyDraftLabel": ".empty-draft-label" in css, "zeroStateCue": True}

    if not observations["B1"]["opacity"] or not observations["B1"]["visibleDisabledReason"]:
        raise RuntimeError("B1 benign CSS self-check failed")
    if not observations["B2"]["noopener"]:
        raise RuntimeError("B2 noopener self-check failed")
    if not observations["B3"]["emptyDraftLabel"]:
        raise RuntimeError("B3 zero-state self-check failed")
    return observations


def item_id(item: dict):
    return item.get("id") or item.get("findingId") or item.get("caseId") or item.get("phase") or item.get("phaseId")


def find_phase(state: dict, phase_id: str):
    for item in state.get("phases", []):
        if not isinstance(item, dict):
            continue
        if item.get("id") == phase_id or item.get("phase") == phase_id or item.get("phaseId") == phase_id:
            return item
    return None


def source_ids_from_state(state: dict):
    text = json_text(state)
    return {source_id for source_id in EXPECTED_SOURCE_IDS if source_id in text}


def evaluate_state(root: Path, contract: dict, errors: list[str]):
    try:
        state = load_json(root / "candidate" / "ux-review-state.json")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"ux-review-state invalid JSON: {exc}")
        return

    require(set(contract["required_state_keys"]) <= set(state), "ux-review-state missing required keys", errors)
    require(state.get("contractId") == contract["contractId"], "ux-review-state contractId mismatch", errors)
    require(state.get("planFingerprint") == contract["planFingerprint"], "ux-review-state planFingerprint mismatch", errors)
    missing_sources = sorted(set(EXPECTED_SOURCE_IDS) - source_ids_from_state(state))
    require(not missing_sources, "ux-review-state missing source ids: " + ", ".join(missing_sources), errors)

    for phase_id in EXPECTED_PHASE_IDS:
        phase = find_phase(state, phase_id)
        require(phase is not None, f"ux-review-state missing phase {phase_id}", errors)
        if phase:
            require(phase.get("owner") or phase.get("ownerPath"), f"ux-review-state phase {phase_id} missing owner", errors)
            require(phase.get("visibleReturnCue") or phase.get("returnCue"), f"ux-review-state phase {phase_id} missing visible return cue", errors)

    state_text = json_text(state)
    markers = [
        "candidate/review-target/docs/stale-ux-notes.md",
        "stale remote source",
        "regression proof",
        "source refresh before owner assignment",
        "blocking remediation before publish",
        "owner-only notes",
        "follow-up diff",
        "changed evidence row",
        "FP1-disabled-opacity-decoy",
        "FP2-noopener-link-decoy",
        "FP3-empty-draft-label-decoy",
        "python verifiers/check_staged_ux_review_reentry.py",
    ]
    for marker in markers:
        require(marker.lower() in state_text.lower(), f"ux-review-state missing marker: {marker}", errors)

    budget = state.get("patchBudget", {})
    require(budget.get("maxChangedPaths") == len(EXPECTED_EDITABLE_PATHS), "patchBudget maxChangedPaths mismatch", errors)
    require(sorted(normalize_path(p) for p in budget.get("requiredChangedPaths", [])) == sorted(EXPECTED_EDITABLE_PATHS), "patchBudget requiredChangedPaths mismatch", errors)


def evaluate_adr(root: Path, contract: dict, errors: list[str]):
    try:
        text = (root / "candidate" / "decision-adr.md").read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"decision-adr read failed: {exc}")
        return
    require(contract["planFingerprint"] in text, "decision-adr planFingerprint missing", errors)
    for source_id in EXPECTED_SOURCE_IDS[:8]:
        require(source_id in text, f"decision-adr missing source id {source_id}", errors)
    markers = [
        "stale remote source must block publish",
        "missing or pending regression proof must block publish",
        "source refresh before owner assignment",
        "blocking remediation before the publish command",
        "auditor export must not expose owner-only notes",
        "follow-up diff after publish must preserve the published receipt",
    ]
    for marker in markers:
        require(marker.lower() in text.lower(), f"decision-adr missing marker: {marker}", errors)


def finding_tuple_digest(finding: dict):
    runtime = finding.get("runtimeEvidence") if isinstance(finding.get("runtimeEvidence"), dict) else {}
    return canonical_digest(
        {
            "caseId": runtime.get("caseId"),
            "file": finding.get("file"),
            "line": finding.get("line"),
            "category": finding.get("category"),
            "severity": finding.get("severity"),
        }
    )


def check_source_evidence(root: Path, finding: dict, errors: list[str]):
    relative_path = normalize_path(finding.get("file", ""))
    line = finding.get("line")
    if not isinstance(relative_path, str) or not isinstance(line, int):
        return
    identifiers = [
        token
        for token in identifiers_from_line(root, relative_path, line)
        if token not in {"def", "return", "if", "or", "in", "len"}
    ]
    if identifiers:
        evidence = str(finding.get("sourceEvidence", "")).lower()
        require(any(token.lower() in evidence for token in identifiers), f"{finding.get('id')}: sourceEvidence not bound to cited line", errors)


def check_findings(root: Path, contract: dict, observations: dict, errors: list[str]):
    try:
        doc = load_json(root / "candidate" / "findings.json")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"findings invalid JSON: {exc}")
        return {}

    require(sorted(doc.keys()) == ["contractId", "findings", "nonFindings", "witnessMatrix"], "findings top-level keys mismatch", errors)
    require(doc.get("contractId") == contract["contractId"], "findings contractId mismatch", errors)
    raw = json_text(doc)
    for snippet in ("ship it", "no ux issues", "looks fine"):
        require(snippet not in raw.lower(), f"prohibited report snippet present: {snippet}", errors)

    findings = doc.get("findings")
    require(isinstance(findings, list), "findings must be a list", errors)
    if not isinstance(findings, list):
        return {}
    require(len(findings) == contract["exact_finding_count"], f"expected {contract['exact_finding_count']} findings, got {len(findings)}", errors)

    allowed_categories = set(contract["allowed_categories"])
    allowed_severities = set(contract["allowed_severities"])
    by_case = {}
    by_id = {}
    for index, finding in enumerate(findings, start=1):
        require(isinstance(finding, dict), f"finding {index} must be an object", errors)
        if not isinstance(finding, dict):
            continue
        require(sorted(finding.keys()) == contract["required_top_level_finding_keys"], f"finding {index}: keys mismatch", errors)
        fid = finding.get("id")
        require(isinstance(fid, str) and re.fullmatch(r"F[1-9]", fid or "") is not None, f"finding {index}: id must be F1..F9", errors)
        require(fid not in by_id, f"duplicate finding id: {fid}", errors)
        by_id[fid] = finding
        finding["file"] = normalize_path(finding.get("file", ""))
        require(finding.get("category") in allowed_categories, f"{fid}: invalid category", errors)
        require(finding.get("severity") in allowed_severities, f"{fid}: invalid severity", errors)
        require(finding.get("owner") in {"ux-reviewer", "accessibility-reviewer", "qa-engineer", "frontend-engineer"}, f"{fid}: invalid owner", errors)
        require(isinstance(finding.get("line"), int), f"{fid}: line must be an integer", errors)
        runtime = finding.get("runtimeEvidence")
        require(isinstance(runtime, dict), f"{fid}: runtimeEvidence must be an object", errors)
        if not isinstance(runtime, dict):
            continue
        require(sorted(runtime.keys()) == ["caseId", "observed", "violatedInvariant"], f"{fid}: runtimeEvidence keys mismatch", errors)
        case_id = runtime.get("caseId")
        require(case_id in EXPECTED_RUNTIME_CASE_IDS, f"{fid}: invalid runtimeEvidence.caseId", errors)
        require(case_id not in by_case, f"duplicate runtime case: {case_id}", errors)
        by_case[case_id] = finding
        require(finding_tuple_digest(finding) in FINDING_TUPLE_DIGESTS.get(case_id, []), f"{fid}: exact finding tuple mismatch", errors)
        require(runtime.get("observed") == observations.get(case_id), f"{fid}: runtime observed object mismatch", errors)
        require(str(runtime.get("violatedInvariant", "")).strip(), f"{fid}: violatedInvariant must be non-empty", errors)
        require(str(finding.get("sourceEvidence", "")).strip(), f"{fid}: sourceEvidence must be non-empty", errors)
        require(str(finding.get("fixBoundary", "")).strip(), f"{fid}: fixBoundary must be non-empty", errors)
        check_source_evidence(root, finding, errors)

    missing_cases = sorted(set(EXPECTED_RUNTIME_CASE_IDS) - set(by_case))
    require(not missing_cases, "missing runtime finding cases: " + ", ".join(missing_cases), errors)
    check_non_findings(doc, contract, errors)
    check_witness_matrix(root, doc, contract, observations, by_case, errors)
    return by_case


def check_non_findings(doc: dict, contract: dict, errors: list[str]):
    items = doc.get("nonFindings")
    require(isinstance(items, list), "nonFindings must be a list", errors)
    if not isinstance(items, list):
        return
    require(len(items) == contract["exact_non_finding_count"], f"expected {contract['exact_non_finding_count']} nonFindings, got {len(items)}", errors)
    by_case = {item.get("caseId"): item for item in items if isinstance(item, dict)}
    require(len(by_case) == len(items), "nonFindings case ids must be distinct", errors)
    expected_terms = {
        "B1": (["disabled", "opacity"], ["visible", "disabled reason"]),
        "B2": (["rel=\"noopener\"", "noopener"], ["link", "hardening"]),
        "B3": (["empty", "draft"], ["zero-state", "neutral"]),
    }
    for case_id, (pattern_terms, reason_terms) in expected_terms.items():
        item = by_case.get(case_id)
        require(item is not None, f"missing nonFinding case {case_id}", errors)
        if item:
            require(sorted(item.keys()) == ["caseId", "pattern", "reason", "sourceBinding"], f"{case_id}: nonFinding keys mismatch", errors)
            require(text_has_all(item.get("pattern"), pattern_terms), f"{case_id}: nonFinding pattern missing terms", errors)
            require(text_has_all(item.get("reason"), reason_terms), f"{case_id}: nonFinding reason missing terms", errors)
            binding = item.get("sourceBinding")
            require(isinstance(binding, dict), f"{case_id}: nonFinding sourceBinding must be an object", errors)
            if isinstance(binding, dict):
                require(normalize_path(binding.get("file", "")).startswith("candidate/review-target/"), f"{case_id}: sourceBinding file mismatch", errors)
                require(isinstance(binding.get("line"), int), f"{case_id}: sourceBinding line must be int", errors)


def expected_witness_status(case_id: str):
    return "benign" if case_id.startswith("B") else "reproduced"


def check_source_binding(root: Path, item: dict, finding: dict | None, case_id: str, errors: list[str]):
    binding = item.get("sourceBinding")
    require(isinstance(binding, dict), f"witness {case_id}: sourceBinding must be an object", errors)
    if not isinstance(binding, dict):
        return
    require(sorted(binding.keys()) == ["file", "function", "line", "sink"], f"witness {case_id}: sourceBinding keys mismatch", errors)
    binding_file = normalize_path(binding.get("file", ""))
    if case_id.startswith("R"):
        require(finding is not None, f"witness {case_id}: no matching finding", errors)
        if finding is None:
            return
        require(binding_file == finding.get("file"), f"witness {case_id}: sourceBinding.file mismatch", errors)
        require(binding.get("line") == finding.get("line"), f"witness {case_id}: sourceBinding.line mismatch", errors)
        expected_function = containing_function(root, finding["file"], finding["line"])
        require(binding.get("function") == expected_function, f"witness {case_id}: sourceBinding.function mismatch", errors)
        require(isinstance(binding.get("sink"), str) and binding["sink"].strip(), f"witness {case_id}: sourceBinding.sink must be non-empty", errors)
    else:
        require(binding_file.startswith("candidate/review-target/"), f"witness {case_id}: benign sourceBinding.file mismatch", errors)
        require(isinstance(binding.get("line"), int), f"witness {case_id}: benign sourceBinding.line must be int", errors)
        require(isinstance(binding.get("function"), str) and binding["function"].strip(), f"witness {case_id}: benign sourceBinding.function missing", errors)


def check_witness_matrix(root: Path, doc: dict, contract: dict, observations: dict, findings_by_case: dict, errors: list[str]):
    items = doc.get("witnessMatrix")
    require(isinstance(items, list), "witnessMatrix must be a list", errors)
    if not isinstance(items, list):
        return
    require(len(items) == contract["exact_witness_count"], f"expected {contract['exact_witness_count']} witness rows, got {len(items)}", errors)
    by_case = {item.get("caseId"): item for item in items if isinstance(item, dict)}
    require(len(by_case) == len(items), "witnessMatrix case ids must be distinct", errors)
    for case_id in EXPECTED_RUNTIME_CASE_IDS + EXPECTED_BENIGN_CASE_IDS:
        item = by_case.get(case_id)
        require(item is not None, f"missing witness case {case_id}", errors)
        if not item:
            continue
        require(sorted(item.keys()) == contract["required_witness_keys"], f"witness {case_id}: keys mismatch", errors)
        require(item.get("status") == expected_witness_status(case_id), f"witness {case_id}: status mismatch", errors)
        if case_id.startswith("R"):
            finding = findings_by_case.get(case_id)
            require(finding is not None and item.get("findingId") == finding.get("id"), f"witness {case_id}: findingId mismatch", errors)
        else:
            finding = None
            require(item.get("findingId") is None, f"witness {case_id}: benign findingId must be null", errors)
        require(item.get("observed") == observations.get(case_id), f"witness {case_id}: observed object mismatch", errors)
        check_source_binding(root, item, finding, case_id, errors)


def response_digest(item: dict):
    return canonical_digest({"id": item.get("id"), "decision": item.get("decision")})


def evaluate_response_gate(root: Path, contract: dict, errors: list[str]):
    try:
        response = load_json(root / "candidate" / "response-gate.json")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"response-gate invalid JSON: {exc}")
        return
    require(sorted(response.keys()) == ["contractId", "gateDecision", "responses"], "response-gate top-level keys mismatch", errors)
    require(response.get("contractId") == contract["contractId"], "response-gate contractId mismatch", errors)
    require(response.get("gateDecision") == contract["expected_gate_decision"], "response-gate gateDecision mismatch", errors)
    rows = response.get("responses")
    require(isinstance(rows, list), "responses must be a list", errors)
    if not isinstance(rows, list):
        return
    require(len(rows) == contract["exact_response_count"], f"expected {contract['exact_response_count']} response rows, got {len(rows)}", errors)
    by_id = {row.get("id"): row for row in rows if isinstance(row, dict)}
    require(len(by_id) == len(rows), "response ids must be distinct", errors)
    for response_id, expected_digest in RESPONSE_DECISION_DIGESTS.items():
        row = by_id.get(response_id)
        require(row is not None, f"missing response row {response_id}", errors)
        if not row:
            continue
        require(sorted(row.keys()) == contract["required_response_keys"], f"{response_id}: response keys mismatch", errors)
        require(row.get("decision") in contract["allowed_response_decisions"], f"{response_id}: invalid response decision", errors)
        require(response_digest(row) == expected_digest, f"{response_id}: response decision mismatch", errors)
        require(row.get("owner") in {"ux-reviewer", "qa-engineer", "frontend-engineer", "accessibility-reviewer"}, f"{response_id}: invalid owner", errors)
        require(isinstance(row.get("sourceIds"), list) and row["sourceIds"], f"{response_id}: sourceIds missing", errors)
        require(isinstance(row.get("visibleReturnCue"), str) and row["visibleReturnCue"].strip(), f"{response_id}: visibleReturnCue missing", errors)


def evaluate_closure(root: Path, contract: dict, errors: list[str]):
    try:
        closure = load_json(root / "candidate" / "closure.json")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"closure invalid JSON: {exc}")
        return
    require(closure.get("contractId") == contract["contractId"], "closure contractId mismatch", errors)
    require(sorted(normalize_path(path) for path in closure.get("changedPaths", [])) == sorted(EXPECTED_EDITABLE_PATHS), "closure changedPaths mismatch", errors)
    require(isinstance(closure.get("validation"), list), "closure validation must be a list", errors)
    validation_text = json_text(closure.get("validation", []))
    for marker in ("python verifiers/check_staged_ux_review_reentry.py", "git diff --check"):
        require(marker in validation_text, f"closure validation marker missing: {marker}", errors)
    closure_text = json_text(closure)
    for marker in EXPECTED_RUNTIME_CASE_IDS + EXPECTED_BENIGN_CASE_IDS + list(RESPONSE_DECISION_DIGESTS) + [contract["planFingerprint"]]:
        require(marker in closure_text, f"closure missing marker: {marker}", errors)
    require(isinstance(closure.get("reviewOutcome"), str) and closure["reviewOutcome"].strip(), "closure reviewOutcome missing", errors)
    require(isinstance(closure.get("residualRisk"), str), "closure residualRisk missing", errors)


def write_metrics(path: Path | None, errors: list[str], observations: dict):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    total = len(EXPECTED_RUNTIME_CASE_IDS) + len(EXPECTED_BENIGN_CASE_IDS) + len(RESPONSE_DECISION_DIGESTS)
    score = 100.0 if not errors else max(0.0, 100.0 - 4.0 * len(errors))
    path.write_text(
        json.dumps(
            {
                "score": score,
                "passed": not errors,
                "errorCount": len(errors),
                "expectedCaseAndResponseRows": total,
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
    contract = load_json(root / "oracle" / "ux-review-reentry-contract.json")
    errors: list[str] = []
    observations: dict = {}

    try:
        check_shape(root, contract, errors)
        observations = compute_runtime_observations(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Runtime witness harness failed: {exc}")

    if args.bundle_shape_only:
        write_metrics(args.metrics_out, errors, observations)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print("N90 verifier PASS (bundle shape)")
        return 0

    check_changed_paths(args.changed_paths, errors)
    evaluate_state(root, contract, errors)
    evaluate_adr(root, contract, errors)
    check_findings(root, contract, observations, errors)
    evaluate_response_gate(root, contract, errors)
    evaluate_closure(root, contract, errors)

    if args.expect_start_state:
        expected = {
            "ux-review-state planFingerprint mismatch",
            "ux-review-state missing source ids",
            "ux-review-state missing phase 01-source-state-ledger",
            "findings top-level keys mismatch",
            "expected 7 findings",
            "response-gate top-level keys mismatch",
            "closure changedPaths mismatch",
        }
        observed = "\n".join(errors)
        missing = [needle for needle in expected if needle not in observed]
        if missing:
            print(f"ERROR: start state no longer exposes expected failures: {missing}", file=sys.stderr)
            return 1
        print("N90 verifier PASS (expected start-state failures present)")
        return 0

    write_metrics(args.metrics_out, errors, observations)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("N90 verifier PASS (100.0 / 100)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
