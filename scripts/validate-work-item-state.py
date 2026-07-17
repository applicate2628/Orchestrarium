#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path


STATUS_VALUES = {"planned", "running", "completed", "revise", "blocked", "cancelled"}
GATE_VALUES = {"PASS", "REVISE", "BLOCKED:dependency", "BLOCKED:prerequisite", "advisory", "none", "WAIVED:user"}
# --- v2 REVISE-closure vocabulary (decision 2026-07-16-review-verdict-closure, minimal slice) ---
EVENT_KINDS = {"launch", "terminal", "standalone"}
EFFORT_ORDER = ["low", "medium", "high", "xhigh", "max"]  # ordered, ascending strength
FINDING_CLASSES = {"publication-safety", "security", "correctness", "performance", "other"}
PROTECTED_CLASSES = {"publication-safety", "security"}  # non-user-waivable (spine: $security-reviewer only)
V2_ONLY_FIELDS = {"eventKind", "launchRunId", "closesRunIds", "artifactRevision", "lane", "effort", "findingClass"}
# Canonical executionRole values (mirrors shared/schemas/agent-runs.schema.json).
# There is exactly ONE main-conversation identity: "main". The main conversation
# also holds the Lead role — orchestration weight is the status.md
# `orchestration: light | full-lead` field, never a second executionRole value.
EXECUTION_ROLES = {"main", "internal", "consultant", "external-worker", "external-reviewer", "external-brigade"}
# Legacy READ-mapping: ledgers written before 2026-07-11 may carry "lead" as the
# executionRole; it reads as "main" (same owner). Read-side acceptance only —
# NEW writes must use "main" (scripts/agent-run-ledger.py rejects legacy values).
LEGACY_EXECUTION_ROLES = {"lead": "main"}
EVIDENCE_KINDS = {"command", "artifact", "visual", "review", "manual-check", "log"}
RETURN_GATE_RE = re.compile(r"^RETURN\([a-z][a-z-]*\)$")
MIN_LENGTHS = {
    "runId": 8,
    "workItem": 1,
    "role": 1,
    "startedAt": 10,
    "updatedAt": 10,
}
ALLOWED_FIELDS = {
    "schemaVersion",
    "runId",
    "workItem",
    "role",
    "executionRole",
    "assignedRole",
    "provider",
    "model",
    "status",
    "gate",
    "scope",
    "promptFile",
    "artifact",
    "evidence",
    "startedAt",
    "updatedAt",
    "notes",
    # v2 closure fields
    "eventKind",
    "launchRunId",
    "closesRunIds",
    "artifactRevision",
    "lane",
    "effort",
    "findingClass",
}
EVIDENCE_ALLOWED_FIELDS = {"kind", "ref", "result"}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def load_jsonl(path: Path, errors: list[str]) -> list[dict]:
    if not path.exists():
        fail(errors, f"missing ledger: {path}")
        return []
    events = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(errors, f"{path}:{line_no}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(event, dict):
            fail(errors, f"{path}:{line_no}: event must be an object")
            continue
        events.append(event)
    if not events:
        fail(errors, f"ledger has no events: {path}")
    return events


def repo_root_for(item: Path) -> Path | None:
    """The repository root that owns this work item.

    Every work item lives under `<root>/work-items/...` (active/ or
    archive/<YYYY-MM>/), so the parent of the `work-items` directory is the
    root. Returns None when the item is not under a `work-items` tree.
    """

    for parent in item.resolve().parents:
        if parent.name == "work-items":
            return parent.parent
    return None


def resolve_work_item_path(item: Path, value: object, label: str, run_id: object, errors: list[str]) -> Path | None:
    """Resolve a recorded path, work-item-relative FIRST, repo-root-relative second.

    A review's artifact is often a repository file rather than a copy inside the
    work item (reviewing `scripts/maintenance/cleanup.py` is the ordinary case
    for an implementation gate). Resolving work-item-relative only made such a
    verdict unrecordable: the PASS closer failed the artifact-exists check and
    the reviewer's verdict was dropped, leaving the obligation open forever.
    Both roots stay inside the repository; absolute paths and escapes are still
    rejected.
    """

    if not isinstance(value, str):
        fail(errors, f"{run_id}: {label} must be a string")
        return None
    if not value.strip():
        fail(errors, f"{run_id}: {label} must be a non-empty relative path")
        return None

    candidate = Path(value)
    if candidate.is_absolute():
        fail(errors, f"{run_id}: {label} must be a relative path: {value}")
        return None

    item_root = item.resolve()
    resolved = (item_root / candidate).resolve()
    if resolved == item_root or item_root in resolved.parents:
        if resolved.exists():
            return resolved
        # Fall through: the same relative string may name a repository file.
    elif resolved != item_root:
        # The string escapes the work item; only the repo-root reading can be
        # legitimate, and it is checked below.
        resolved = None

    root = repo_root_for(item)
    if root is not None:
        from_root = (root / candidate).resolve()
        if from_root == root or root in from_root.parents:
            if from_root.exists() or resolved is None:
                return from_root

    if resolved is None:
        fail(errors, f"{run_id}: {label} escapes the work item and the repository: {value}")
        return None
    return resolved


def validate_evidence(evidence: object, run_id: object, errors: list[str], require_non_empty: bool) -> None:
    if not isinstance(evidence, list):
        fail(errors, f"{run_id}: evidence must be a list")
        return
    if not evidence:
        if require_non_empty:
            fail(errors, f"{run_id}: PASS gate requires evidence")
        return

    for index, entry in enumerate(evidence, start=1):
        if not isinstance(entry, dict):
            fail(errors, f"{run_id}: evidence[{index}] must be an object")
            continue
        for key in sorted(set(entry) - EVIDENCE_ALLOWED_FIELDS):
            fail(errors, f"{run_id}: evidence[{index}] has unexpected field: {key}")
        if entry.get("kind") not in EVIDENCE_KINDS:
            fail(errors, f"{run_id}: evidence[{index}] has invalid kind {entry.get('kind')!r}")
        if not isinstance(entry.get("ref"), str) or not entry.get("ref", "").strip():
            fail(errors, f"{run_id}: evidence[{index}] requires ref")
        if "result" in entry and not isinstance(entry.get("result"), str):
            fail(errors, f"{run_id}: evidence[{index}].result must be a string")


def validate_event(event: dict, item: Path, seen: set[str], errors: list[str]) -> None:
    required = ["schemaVersion", "runId", "workItem", "role", "executionRole", "status", "gate", "scope", "startedAt", "updatedAt"]
    for key in required:
        if key not in event:
            fail(errors, f"event missing required field: {key}")

    for key in sorted(set(event) - ALLOWED_FIELDS):
        fail(errors, f"unexpected field: {key}")

    run_id = event.get("runId")
    if isinstance(run_id, str):
        if run_id in seen:
            fail(errors, f"duplicate runId: {run_id}")
        seen.add(run_id)
    else:
        fail(errors, f"{run_id}: runId must be a string")

    schema_version = event.get("schemaVersion")
    if schema_version not in (1, 2):
        fail(errors, f"{run_id}: schemaVersion must be 1 or 2")
    if schema_version == 1:
        for key in sorted(V2_ONLY_FIELDS & set(event)):
            fail(errors, f"{run_id}: field {key} requires schemaVersion 2")
    for key, min_length in MIN_LENGTHS.items():
        value = event.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(errors, f"{run_id}: {key} must be a non-empty string")
        elif len(value) < min_length:
            fail(errors, f"{run_id}: {key} must be at least {min_length} characters")
    for key in ["assignedRole", "provider", "model", "promptFile", "notes"]:
        if key in event and not isinstance(event.get(key), str):
            fail(errors, f"{run_id}: {key} must be a string")
    if event.get("status") not in STATUS_VALUES:
        fail(errors, f"{run_id}: invalid status {event.get('status')!r}")
    gate = event.get("gate")
    if not isinstance(gate, str) or (gate not in GATE_VALUES and not RETURN_GATE_RE.fullmatch(gate)):
        fail(errors, f"{run_id}: invalid gate {event.get('gate')!r}")
    execution_role = event.get("executionRole")
    if execution_role in LEGACY_EXECUTION_ROLES:
        execution_role = LEGACY_EXECUTION_ROLES[execution_role]  # legacy read-mapping (lead -> main)
    if execution_role not in EXECUTION_ROLES:
        fail(errors, f"{run_id}: invalid executionRole {event.get('executionRole')!r}")
    if not isinstance(event.get("scope"), list) or not event.get("scope"):
        fail(errors, f"{run_id}: scope must be a non-empty list")
    elif any(not isinstance(scope, str) or not scope.strip() for scope in event["scope"]):
        fail(errors, f"{run_id}: scope items must be non-empty strings")

    status = event.get("status")
    artifact = event.get("artifact")
    evidence = event.get("evidence")

    artifact_path = None
    if artifact:
        artifact_path = resolve_work_item_path(item, artifact, "artifact", run_id, errors)
    elif "artifact" in event and not isinstance(artifact, str):
        fail(errors, f"{run_id}: artifact must be a string")

    if evidence is not None:
        validate_evidence(evidence, run_id, errors, gate == "PASS")

    if gate == "PASS":
        if status != "completed":
            fail(errors, f"{run_id}: PASS gate requires completed status")
        if not artifact:
            fail(errors, f"{run_id}: PASS gate requires artifact")
        if artifact_path is not None and not artifact_path.exists():
            fail(errors, f"{run_id}: artifact does not exist: {artifact}")
        if evidence is None:
            fail(errors, f"{run_id}: PASS gate requires evidence")

    if gate == "REVISE" and status not in {"revise", "completed"}:
        fail(errors, f"{run_id}: REVISE gate requires revise or completed status")
    if isinstance(gate, str) and gate.startswith("BLOCKED") and status != "blocked":
        fail(errors, f"{run_id}: BLOCKED gate requires blocked status")

    # --- v2 per-event field checks (closure semantics are ledger-level, see validate_closure) ---
    event_kind = event.get("eventKind")
    if "eventKind" in event and event_kind not in EVENT_KINDS:
        fail(errors, f"{run_id}: invalid eventKind {event_kind!r}")
    if "launchRunId" in event:
        if not isinstance(event.get("launchRunId"), str) or len(event["launchRunId"]) < 8:
            fail(errors, f"{run_id}: launchRunId must be a string of >= 8 chars")
        if event_kind != "terminal":
            fail(errors, f"{run_id}: launchRunId is only legal on eventKind terminal")
    if event_kind == "terminal" and "launchRunId" not in event:
        fail(errors, f"{run_id}: eventKind terminal requires launchRunId")
    if "closesRunIds" in event:
        closes = event.get("closesRunIds")
        if not isinstance(closes, list) or not closes or any(
            not isinstance(x, str) or len(x) < 8 for x in closes
        ):
            fail(errors, f"{run_id}: closesRunIds must be a non-empty list of runId strings")
        elif len(set(closes)) != len(closes):
            fail(errors, f"{run_id}: closesRunIds must not contain duplicates")
        if gate not in {"PASS", "WAIVED:user"}:
            fail(errors, f"{run_id}: closesRunIds is only legal on PASS or WAIVED:user events")
    for key in ("artifactRevision", "lane"):
        if key in event and (not isinstance(event.get(key), str) or not event[key].strip()):
            fail(errors, f"{run_id}: {key} must be a non-empty string")
    if "effort" in event and event.get("effort") not in EFFORT_ORDER:
        fail(errors, f"{run_id}: invalid effort {event.get('effort')!r}")
    if "findingClass" in event and event.get("findingClass") not in FINDING_CLASSES:
        fail(errors, f"{run_id}: invalid findingClass {event.get('findingClass')!r}")

    if gate == "WAIVED:user":
        # Typed user disposition (decision item 4): sole legal terminal status is
        # 'completed'; it must name its exact targets; and the user's explicit
        # authorization must be carried as manual-check evidence. Free-text notes
        # carry no authority.
        if status != "completed":
            fail(errors, f"{run_id}: WAIVED:user requires completed status")
        if "closesRunIds" not in event:
            fail(errors, f"{run_id}: WAIVED:user requires closesRunIds")
        entries = event.get("evidence") if isinstance(event.get("evidence"), list) else []
        manual_refs = " ".join(
            e.get("ref", "") for e in entries
            if isinstance(e, dict) and e.get("kind") == "manual-check" and isinstance(e.get("ref"), str)
        )
        if not manual_refs:
            fail(errors, f"{run_id}: WAIVED:user requires a manual-check evidence entry with the user's authorization")
        else:
            # The authorization must NAME the exact obligations it waives (design:
            # target-bound evidence; unrelated authorization text is not authority).
            closes = event.get("closesRunIds") if isinstance(event.get("closesRunIds"), list) else []
            for target_id in closes:
                if not isinstance(target_id, str):
                    continue
                # Exact token identity, not substring: 'run-x-extra' in the evidence
                # must NOT authorize target 'run-x' (Sol impl-gate r2 prefix collision).
                token_re = re.compile(rf"(?<![\w.-]){re.escape(target_id)}(?![\w.-])")
                if not token_re.search(manual_refs):
                    fail(errors, f"{run_id}: WAIVED:user manual-check evidence does not name target {target_id} exactly — authorization must be target-bound")


def validate_closure(events: list[dict], errors: list[str], telemetry: dict[str, int] | None = None) -> tuple[list[dict], list[dict]]:
    """Ledger-level REVISE-closure validation (decision 2026-07-16-review-verdict-closure,
    minimal slice). Returns (open_v2_revise_events, open_launch_events) — obligations never discharged/settled events (never discharged by a valid
    closer). Closure is derived ONLY from the closesRunIds relation — never from
    role/scope/artifact string matching (proven unstable by live replay in the design loop).
    """
    tel = telemetry if telemetry is not None else {}

    def bump(rule: str) -> None:
        tel[rule] = tel.get(rule, 0) + 1

    index: dict[str, tuple[int, dict]] = {}
    for pos, event in enumerate(events):
        rid = event.get("runId")
        if isinstance(rid, str) and rid not in index:
            index[rid] = (pos, event)

    # Lifecycle integrity (only when eventKind is used): one terminal per launch,
    # terminal references an earlier launch.
    terminals_by_launch: dict[str, str] = {}
    for pos, event in enumerate(events):
        if event.get("eventKind") != "terminal":
            continue
        rid = event.get("runId")
        launch_id = event.get("launchRunId")
        if not isinstance(launch_id, str):
            continue  # per-event check already failed it
        bump("lifecycle-terminal-checked")
        target = index.get(launch_id)
        if target is None or target[0] >= pos:
            fail(errors, f"{rid}: launchRunId {launch_id} does not reference an earlier event")
            bump("lifecycle-dangling-launch")
            continue
        if target[1].get("eventKind") != "launch":
            fail(errors, f"{rid}: launchRunId {launch_id} references a non-launch event")
            bump("lifecycle-nonlaunch-ref")
        if launch_id in terminals_by_launch:
            fail(errors, f"{rid}: duplicate terminal for launch {launch_id} (first: {terminals_by_launch[launch_id]})")
            bump("lifecycle-duplicate-terminal")
        else:
            terminals_by_launch[launch_id] = rid if isinstance(rid, str) else "<invalid>"

    discharged: dict[str, str] = {}  # target runId -> closer runId
    for pos, event in enumerate(events):
        closes = event.get("closesRunIds")
        if not isinstance(closes, list) or not closes:
            continue
        rid = event.get("runId")
        gate = event.get("gate")
        for target_id in closes:
            if not isinstance(target_id, str):
                continue
            bump("closure-checked")
            entry = index.get(target_id)
            # C1: target exists and is EARLIER in the ledger.
            if entry is None or entry[0] >= pos:
                fail(errors, f"{rid}: closesRunIds target {target_id} does not reference an earlier event (C1)")
                bump("C1-fail")
                continue
            target = entry[1]
            # C2: target is an open REVISE; one obligation, one closer.
            if target.get("gate") != "REVISE":
                fail(errors, f"{rid}: closesRunIds target {target_id} is not a REVISE event (C2)")
                bump("C2-fail")
                continue
            if target_id in discharged:
                fail(errors, f"{rid}: REVISE {target_id} already discharged by {discharged[target_id]} (C2 unique discharge)")
                bump("C2-duplicate-discharge")
                continue
            # C5 hard boundary: protected finding classes are non-user-waivable.
            if gate == "WAIVED:user" and target.get("findingClass") not in (FINDING_CLASSES - PROTECTED_CLASSES):
                # Fail closed two ways: a PROTECTED class is non-user-waivable, and an
                # UNCLASSIFIED (or unknown) finding is treated as protected — omission
                # must never be the cheaper path around the boundary.
                fail(errors, f"{rid}: WAIVED:user cannot discharge finding {target_id} (findingClass={target.get('findingClass')!r}: protected or unclassified) — $security-reviewer authority only (C5)")
                bump("C5-protected-waiver-fail")
                continue
            # C3 (PASS closers): identity + authority + strength against the target.
            if gate == "PASS":
                closer_exec = event.get("executionRole")
                if closer_exec in LEGACY_EXECUTION_ROLES:
                    closer_exec = LEGACY_EXECUTION_ROLES[closer_exec]
                # Reviewer-side ONLY (design; governance: consultant is advisory-only and
                # never a gate authority; brigade is a dispatch surface, not a verdict role).
                if closer_exec not in {"external-reviewer", "internal"}:
                    fail(errors, f"{rid}: closer executionRole {event.get('executionRole')!r} cannot discharge a review verdict — reviewer-side (external-reviewer|internal) only (C3)")
                    bump("C3-executionrole-fail")
                    continue
                t_art, c_art = target.get("artifact"), event.get("artifact")
                if isinstance(t_art, str) and t_art.strip():
                    if not isinstance(c_art, str) or c_art != t_art:
                        fail(errors, f"{rid}: closer artifact {c_art!r} != target artifact {t_art!r} (C3)")
                        bump("C3-artifact-fail")
                        continue
                t_lane, c_lane = target.get("lane"), event.get("lane")
                if isinstance(t_lane, str) and t_lane.strip():
                    if not isinstance(c_lane, str) or c_lane != t_lane:
                        fail(errors, f"{rid}: closer lane {c_lane!r} != target lane {t_lane!r} (C3)")
                        bump("C3-lane-fail")
                        continue
                t_role = target.get("role")
                if event.get("role") != t_role and event.get("assignedRole") != t_role:
                    fail(errors, f"{rid}: closer lacks authority over {target_id} (role/assignedRole != {t_role!r}) (C3)")
                    bump("C3-authority-fail")
                    continue
                # Audit counters for the DEFERRED cathedral (fable impl gate): observe,
                # without enforcing, how often the deferred rules would have mattered.
                if target.get("provider") != event.get("provider"):
                    bump("audit-cross-provider-closure")
                t_rev, c_rev = target.get("artifactRevision"), event.get("artifactRevision")
                if isinstance(t_rev, str) and isinstance(c_rev, str) and t_rev != c_rev:
                    bump("audit-artifact-revision-drift")
                t_eff, c_eff = target.get("effort"), event.get("effort")
                if t_eff in EFFORT_ORDER:
                    # Totality (fail closed): a target that declares its tier cannot be
                    # closed by an undeclared-tier closer — omission is not a bypass.
                    if c_eff not in EFFORT_ORDER:
                        fail(errors, f"{rid}: target declares effort {t_eff} but closer omits effort (C3 totality)")
                        bump("C3-effort-omitted-fail")
                        continue
                    if (
                        target.get("provider") == event.get("provider")
                        and EFFORT_ORDER.index(c_eff) < EFFORT_ORDER.index(t_eff)
                    ):
                        fail(errors, f"{rid}: closer effort {c_eff} < target effort {t_eff} (C3 same-provider tier)")
                        bump("C3-effort-fail")
                        continue
            discharged[target_id] = rid if isinstance(rid, str) else "<invalid>"
            bump("closure-accepted")

    # Open v2 REVISE obligations. Scoped to schemaVersion 2 on purpose: the pre-existing
    # v1 ledgers migrate by hand with user sign-off (fable minimal-slice gate) instead of
    # retroactively failing every historical item.
    open_revise = [
        event for event in events
        if event.get("schemaVersion") == 2
        and event.get("gate") == "REVISE"
        and event.get("runId") not in discharged
    ]
    tel["open-revise"] = tel.get("open-revise", 0) + len(open_revise)
    # Unsettled launches (no terminal) are strict-mode blockers too: a lost terminal
    # must not make a possibly-REVISE run invisible to the push gate.
    open_launches = [
        event for event in events
        if event.get("eventKind") == "launch"
        and isinstance(event.get("runId"), str)
        and event["runId"] not in terminals_by_launch
    ]
    tel["open-launches"] = tel.get("open-launches", 0) + len(open_launches)
    return open_revise, open_launches


def validate_status(item: Path, events: list[dict], errors: list[str]) -> None:
    status_path = item / "status.md"
    if not status_path.exists():
        fail(errors, f"missing status.md: {status_path}")
        return
    text = status_path.read_text(encoding="utf-8")
    for section in ["## Current state", "## Active agents", "## Completed agents", "## Next action"]:
        if section not in text:
            fail(errors, f"status.md missing section: {section}")

    running_events = [event for event in events if event.get("status") == "running"]
    if running_events and "Primary task status**: closed" in text:
        fail(errors, "status.md cannot be closed while ledger has running agents")


def validate_work_item(
    item: Path,
    ledger_path: Path | None = None,
    strict_revise: bool = True,
    telemetry: dict[str, int] | None = None,
) -> list[str]:
    """ledger_path: candidate-validation seam — validate THIS file instead of the live
    ledger (the atomic-write flow validates its temp candidate before os.replace).
    strict_revise: open v2 REVISE obligations are errors (decision item 3: a validation
    tool's job is failing); pass False only for triage sessions.
    """
    errors: list[str] = []
    events = load_jsonl(ledger_path or (item / "agent-runs.jsonl"), errors)
    seen: set[str] = set()
    for event in events:
        validate_event(event, item, seen, errors)
    open_revise, open_launches = validate_closure(events, errors, telemetry)
    if strict_revise:
        for event in open_launches:
            fail(
                errors,
                f"unsettled launch: {event.get('runId')} (lane={event.get('lane')!r}) — no terminal "
                f"event; a lost verdict must not be invisible to the gate (re-settle or cancel it)",
            )
        for event in open_revise:
            fail(
                errors,
                f"open REVISE obligation: {event.get('runId')} (lane={event.get('lane')!r}, "
                f"artifact={event.get('artifact')!r}) — closes only on re-verification PASS "
                f"(closesRunIds) or a typed disposition, never on author belief or validator green",
            )
    validate_status(item, events, errors)
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-item", required=True, help="Path to one work-items/active/<item> directory")
    parser.add_argument("--ledger-path", help="Validate this candidate ledger file instead of the item's live agent-runs.jsonl")
    parser.add_argument("--no-strict-revise", action="store_true", help="Do not fail on open v2 REVISE obligations (triage only)")
    parser.add_argument("--telemetry", action="store_true", help="Print closure rule-fire counters")
    args = parser.parse_args(argv)

    item = Path(args.work_item).resolve()
    telemetry: dict[str, int] = {}
    errors = validate_work_item(
        item,
        ledger_path=Path(args.ledger_path).resolve() if args.ledger_path else None,
        strict_revise=not args.no_strict_revise,
        telemetry=telemetry,
    )
    if args.telemetry and telemetry:
        counters = ", ".join(f"{k}={v}" for k, v in sorted(telemetry.items()))
        print(f"TELEMETRY: {counters}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"RESULT: FAIL ({len(errors)} errors)")
        return 1
    print(f"RESULT: PASS ({item})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
