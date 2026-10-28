import importlib.util
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import copy
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check-work-items-state.py"
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"
MUTATOR = ROOT / "scripts" / "mutate-work-item.py"


def run_checker(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root), *args],
        text=True,
        capture_output=True,
    )


def write_checker_bundle(bundle_dir: Path, sentinel_source: str | None = None) -> Path:
    """Copy the checker into an isolated installed-layout fixture."""
    bundle_dir.mkdir(parents=True)
    schema_dir = bundle_dir.parent / "shared" / "schemas"
    schema_dir.mkdir(parents=True)
    shutil.copy2(
        ROOT / "shared" / "schemas" / "agent-runs.schema.json",
        schema_dir / "agent-runs.schema.json",
    )
    checker = bundle_dir / CHECKER.name
    shutil.copy2(CHECKER, checker)
    shutil.copy2(VALIDATOR, bundle_dir / VALIDATOR.name)
    shutil.copy2(MUTATOR, bundle_dir / MUTATOR.name)
    if sentinel_source is not None:
        (bundle_dir / "workitem_sentinels.py").write_text(sentinel_source, encoding="utf-8")
    return checker


def run_bundled_checker(checker: Path, root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(checker), "--root", str(root)],
        text=True,
        capture_output=True,
    )


def load_checker_module():
    spec = importlib.util.spec_from_file_location("check_work_items_state_direct", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_validator_module():
    spec = importlib.util.spec_from_file_location("work_item_validator_direct", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_false_event_validity_cannot_settle_revise_or_register_terminal(tmp_path: Path):
    validator = load_validator_module()
    item = write_valid_item(tmp_path)
    common = ledger_event(schemaVersion=2, lane="implementation", effort="high")
    launch = {**common, "runId": "launch-001", "eventKind": "launch",
              "status": "running", "gate": "none"}
    revise = {**common, "runId": "revise-001", "eventKind": "standalone",
              "gate": "REVISE", "status": "revise", "findingClass": "correctness"}
    closer = {**common, "runId": "closer-001", "closesRunIds": ["revise-001"],
              "eventKind": "terminal", "launchRunId": "launch-001"}
    events = [launch, revise, closer]
    ledger = item / "agent-runs.jsonl"
    before = ("".join(json.dumps(event) + "\n" for event in events)).encode()
    ledger.write_bytes(before)
    context = validator.load_effective_ledger_view(
        tmp_path, item, ledger.relative_to(tmp_path).as_posix()
    )
    errors: list[str] = []
    validity = validator.derive_event_validity(context.rows, item, errors, context=context)
    assert errors == []
    assert all(row.current_schema_valid for row in validity)
    open_revise, open_launches = validator.validate_closure(
        context.rows, errors, event_validity=[True, True, False], context=context
    )
    assert errors == []
    assert [event["runId"] for event in open_revise] == ["revise-001"]
    assert [event["runId"] for event in open_launches] == ["launch-001"]
    assert validator.validate_closure(
        context.rows, errors, event_validity=[True, True, True], context=context
    ) == ([], [])
    assert errors == []
    # Caller booleans can restrict an issued result, never create authority.
    refused: list[str] = []
    assert validator.validate_closure(events, refused, event_validity=[True] * 3) == ([], [])
    assert any("EFFECTIVE-VIEW-BYPASS" in error for error in refused)
    assert ledger.read_bytes() == before


def test_invalid_launch_does_not_enter_authority_reduction():
    validator = load_validator_module()
    launch = {"schemaVersion": 2, "runId": "launch-001", "eventKind": "launch"}
    terminal = {
        "schemaVersion": 2, "runId": "terminal-001", "eventKind": "terminal",
        "launchRunId": "launch-001", "status": "completed", "gate": "PASS",
    }
    errors: list[str] = []

    _open_revise, open_launches = validator.validate_closure(
        [launch, terminal], errors, event_validity=[False, True]
    )

    assert open_launches == []


def valid_status() -> str:
    return "\n".join(
        [
            "# Status",
            "status: active",
            "",
            "## Current state",
            "**Primary task status**: open",
            "",
            "## Active agents",
            "- none",
            "",
            "## Completed agents",
            "- none",
            "",
            "## Next action",
            "Continue.",
            "",
        ]
    )


def minimal_staged_status(**updates: str) -> str:
    fields = {
        "template": "staged",
        "status": "active",
        "started": "2026-07-31T10:00:00Z",
        "updated": "2026-07-31T10:05:00Z",
        "Task": "Keep the staged checker contract aligned.",
        "Current step": "Verify the shared status validator.",
        "Last result": "Staged work item admitted.",
        "Next action": "Run the staged checker gate.",
        "Scope boundary": "Work-item lifecycle scripts and focused tests.",
        "Owner": "toolchain-engineer",
        "Integration owner": "lead",
        "Evidence gate": "Focused and full lifecycle suites.",
    }
    fields.update(updates)
    frontmatter = [
        "---",
        f"template: {fields.pop('template')}",
        f"status: {fields.pop('status')}",
        f"started: {fields.pop('started')}",
        f"updated: {fields.pop('updated')}",
        "---",
        "",
    ]
    return "\n".join(frontmatter + [f"{key}: {value}" for key, value in fields.items()]) + "\n"


def ledger_event(**updates):
    event = {
        "schemaVersion": 1,
        "runId": "run-check-001",
        "workItem": "active-item",
        "role": "qa-engineer",
        "executionRole": "internal",
        "status": "completed",
        "gate": "PASS",
        "scope": ["tests/test_work_items_state_checker.py"],
        "artifact": "reviews/qa.md",
        "evidence": [{"kind": "command", "ref": "pytest -q"}],
        "startedAt": "2026-05-03T10:00:00Z",
        "updatedAt": "2026-05-03T10:05:00Z",
    }
    event.update(updates)
    return event


def write_valid_item(root: Path, name: str = "active-item", event: dict | None = None) -> Path:
    item = root / "work-items" / "active" / name
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(valid_status(), encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    (item / "agent-runs.jsonl").write_text(json.dumps(event or ledger_event(workItem=name)) + "\n", encoding="utf-8")
    return item


def write_staged_item(
    root: Path,
    name: str = "staged-item",
    status: str | None = None,
    event: dict | None = None,
) -> Path:
    item = root / "work-items" / "active" / name
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(status or minimal_staged_status(), encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    selected_event = event or ledger_event(workItem=name)
    (item / "agent-runs.jsonl").write_text(
        json.dumps(selected_event) + "\n",
        encoding="utf-8",
    )
    return item


def _goal_fixture(tmp_path: Path, *, criterion_ids=("alpha", "omega", "useful"), legacy=False, preservation=False, flat=None):
    """Accepted synthetic admission; actual lifecycle calls are runtime-only."""
    checker = load_checker_module()
    owner = checker.load_lifecycle_owner()
    roots = {key: tmp_path / key for key in ("A", "B")}
    if flat is not None:
        roots["B"] = flat.root
    for rid, root in roots.items():
        root.mkdir(exist_ok=flat is not None and rid == "B")
        if not preservation or rid != "B":
            (root / "work-items" / "epics").mkdir(parents=True, exist_ok=flat is not None and rid == "B")
        (root / "inputs").mkdir()
    record = roots["A"] / "work-items" / "epics" / "goal-epic.md"
    record.write_text("status: active\nlabel: Synthetic goal.\n", encoding="utf-8")
    for rid, slug in (("A", "a"), ("B", "b"), ("A", "g")):
        if preservation and rid == "B":
            continue
        owner.create_candidate(roots[rid], slug, f"Task: {slug}\nNext action: Start.\nupdated: 2026-10-08T00:00:00Z\n".encode())
        status = ("---\ntemplate: quick-fix\nstatus: active\nstarted: 2026-10-08T00:00:00Z\n"
                  "updated: 2026-10-08T00:00:00Z\n---\n- **Task**: Useful fixture.\n- **Current step**: Verify.\n"
                  "- **Last result**: Fixture ready.\n- **Next action**: Complete.\n")
        owner.start_item(roots[rid], slug, status.encode())
        item = roots[rid] / "work-items" / "active" / slug
        (item / "outcome.md").write_text("Accepted useful synthetic outcome/oracle.\n", encoding="utf-8")
    def ref(rid: str, path: str, item=None):
        base = roots[rid] if item is None else next(path for path in owner._category_locations(roots[rid], owner.CATEGORIES["work-item"], item))
        return {"rootId": rid, "workItem": item, "path": path,
                "sha256": hashlib.sha256((base / path).read_bytes()).hexdigest()}
    for name in ("root", "accepted", "checks", "source", "inventory", "audit"):
        (roots["A"] / "inputs" / f"{name}.md").write_text(f"Accepted fixture {name}.\n", encoding="utf-8")
    acceptance = ref("A", "inputs/accepted.md")
    rules = {"emptyActiveCriterion": criterion_ids[0], "settlementCriterion": criterion_ids[1]}
    members = [{"rootId": rid, "slug": slug, "outcome": "delivered", "acceptance": ref(rid, "outcome.md", slug), "receipt": None}
               for rid, slug in (("A", "a"), ("B", "b"), ("A", "g")) if not preservation or rid != "B"]
    if flat is not None:
        members.append({"rootId": "B", "slug": flat.slug, "outcome": "delivered",
                        "acceptance": ref("B", "evidence/acceptance.md"), "receipt": None})
    if legacy:
        historical = roots["A"] / "work-items" / "archive" / "2026-06" / "historical-member"
        historical.mkdir(parents=True)
        (historical / "closure.md").write_text("Closed: 2026-06-01\nOutcome: Accepted historical useful result.\n", encoding="utf-8")
        (historical / "outcome.md").write_text("Original accepted outcome and applicable checks.\n", encoding="utf-8")
        members.append({"rootId": "A", "slug": historical.name, "outcome": "delivered", "acceptance": ref("A", "outcome.md", historical.name), "receipt": None})
    admission = {"schema": "orchestrarium-goal-admission", "version": 1, "admissionId": "synthetic-admission",
        "revision": 1, "humanSha256": None, "previousAdmission": None, "amendment": None,
        "criterionIds": list(criterion_ids), "rootIds": list(roots), "goalItem": {"rootId": "A", "slug": "g"},
        "originalMembers": [{"rootId": row["rootId"], "slug": row["slug"]} for row in members],
        "unresolvedRoots": [], "rules": rules}
    human = ("Original synthetic criteria: " + ",".join(criterion_ids) + "; roots A,B; members "
             + ",".join(f"{row['rootId']}/{row['slug']}" for row in members) + ".\n").encode()
    admission["humanSha256"] = hashlib.sha256(human).hexdigest()
    brief = roots["A"] / "inputs" / "brief.md"
    brief.write_bytes(human + b"<!-- orchestrarium-goal-admission:v1 -->\n" + json.dumps(admission).encode()
                      + b"\n<!-- /orchestrarium-goal-admission:v1 -->\n")
    goal = {"schema": "orchestrarium-goal-completion", "version": 1, "admissionId": admission["admissionId"],
        "admission": ref("A", "inputs/brief.md"), "criterionIds": list(criterion_ids), "coordinatorRootId": "A",
        "roots": [{"id": key, "locator": str(root), "identity": str(root.resolve()), "admission": ref("A", "inputs/root.md")}
                  for key, root in roots.items()], "goalItem": admission["goalItem"], "members": members,
        "criteria": [{"id": cid, "state": "verified", "acceptance": acceptance,
                      "checks": [ref("A", "inputs/checks.md")], "sourcePins": [ref("A", "inputs/source.md")], "actions": []}
                     for cid in criterion_ids], "rules": rules,
        "coverage": {"inventory": ref("A", "inputs/inventory.md"), "audit": ref("A", "inputs/audit.md"), "pending": []}}
    def write_goal(terminal=False, *, omit_refresh=()):
        nonlocal record
        prefix = b"status: active\nlabel: Synthetic goal.\n"
        if terminal:
            destination = roots["A"] / "work-items" / "epics" / "archive" / "2026-10" / record.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if record != destination:
                record.unlink()
            record = destination
            prefix = b"status: closed\nclosed: 2026-10-08T00:05:00Z\noutcome: Delivered.\nevidence: Accepted fixture.\n"
        record.write_bytes(prefix + b"<!-- orchestrarium-goal-contract:v1 -->\n" + json.dumps(goal).encode()
                           + b"\n<!-- /orchestrarium-goal-contract:v1 -->\n")
        for rid, root in roots.items():
            if rid in omit_refresh:
                continue
            if (root / "work-items").is_dir():
                owner.refresh_readme(root)
        return record
    def close_member(rid, slug):
        item = roots[rid] / "work-items" / "active" / slug
        instant = "2026-10-08T00:05:00Z"
        (item / "bug-dispositions.json").write_text(json.dumps({"schemaVersion": 1, "workItem": slug, "closedAt": instant, "bugs": []}), encoding="utf-8")
        archived = owner.close_item(roots[rid], slug,
            f"Closed: {instant}\nOutcome: Useful delivered fixture.\nEvidence: Accepted synthetic oracle.\nResidual risk: None.\n".encode(), instant)
        next(row for row in goal["members"] if (row["rootId"], row["slug"]) == (rid, slug))["receipt"] = ref(rid, owner.BUG_DISPOSITIONS_RECEIPT, slug)
        return archived
    write_goal()
    return checker, owner, roots, goal, write_goal, close_member


class TestLegacyFlatGoalConsumer(unittest.TestCase):
    def setUp(self):
        # Ordinary import reuses the one real producer module/class already
        # loaded by its own tests. A second fixed-name owner alias invalidates
        # genuine issuer registrations and is not a fixture isolation mechanism.
        from tests.test_legacy_flat_terminal_close import LegacyFlatTerminalTests
        self.flat = LegacyFlatTerminalTests()
        self.flat.setUp()
        self.addCleanup(self.flat.doCleanups)
        temporary = tempfile.TemporaryDirectory(prefix="flat-goal-consumer-", dir=ROOT / ".scratch")
        self.addCleanup(temporary.cleanup)
        self.goal_temporary = Path(temporary.name)

    def complete_flat(self, *, history=False, pending=False):
        if history:
            # Reuse the actual admitted serializer fixture and its original
            # required-history criterion; no synthetic terminal or empty ledger.
            self.flat.test_actual_flat_native_history_accepts_evidenced_absence_and_real_settled_rows()
        # Bind the Goal reference only after its original criteria/history bytes
        # are ready. The earlier fixture's stale acceptance SHA correctly refused.
        self.checker, self.owner, self.roots, self.goal, self.write_goal, self.close_member = _goal_fixture(
            self.goal_temporary, legacy=True, flat=self.flat)
        for rid, slug in (("A", "a"), ("B", "b"), ("A", "g")):
            self.close_member(rid, slug)
        self.flat_row = next(row for row in self.goal["members"] if row["slug"] == self.flat.slug)
        _raw, arguments = self.flat.legacy_request()
        if history:
            request_path = self.flat.root / "legacy-evidence.json"
            request = json.loads(request_path.read_bytes())
            request["historySelection"]["ledgerRequired"] = True
            request["historySelection"]["absentPaths"] = []
            request["historySelection"]["artifacts"] += [self.flat.reference(self.flat.source.parent / name)
                                                         for name in ("agent-runs.jsonl", "proof.md")]
            request_path.write_text(json.dumps(request, sort_keys=True) + "\n", encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(MUTATOR), *arguments, "--apply",
            *( ["--inject-failure-at", "after-board"] if pending else [])],
            text=True, capture_output=True, timeout=240, check=False)
        assert result.returncode == (1 if pending else 0), result.stdout + result.stderr
        self.archive = self.flat.root / "work-items/archive/2026-10" / self.flat.slug
        if not pending:
            action = self.archive / self.owner.LEGACY_COMPLETION_RECEIPT
            self.flat_row["receipt"] = {"rootId": "B", "workItem": self.flat.slug,
                "path": action.name, "sha256": hashlib.sha256(action.read_bytes()).hexdigest()}
        assert not self.flat.source.exists()
        self.record = self.write_goal(terminal=True, omit_refresh=("B",) if pending else ())

    def public_observation(self):
        result = subprocess.run([sys.executable, "-B", str(CHECKER), "--root", str(self.roots["A"]),
            "--goal", str(self.record), "--goal-phase", "final", "--json"],
            text=True, capture_output=True, timeout=240, check=False)
        assert result.stdout.strip(), result.stderr
        return result, json.loads(result.stdout)

    def assert_flat_credit(self, observation):
        assert observation["decision"] == "eligible", observation
        row = next(row for row in observation["members"] if row["slug"] == self.flat.slug)
        assert row == {"rootId": "B", "slug": self.flat.slug, "state": "delivered-closed",
                       "proofProfile": "legacy-flat-completion-v1"}, row
        quoted = {ref["path"] for ref in observation["quote"]["references"]
                  if ref["rootId"] == "B" and ref["workItem"] == self.flat.slug}
        assert {"closure.md", self.owner.LEGACY_COMPLETION_RECEIPT, self.owner.BUG_DISPOSITIONS_RECEIPT} <= quoted
        port = self.owner.observe_work_item_terminal(self.roots["B"], f"work-item:{self.flat.slug}")
        assert {path.relative_to(self.archive).as_posix() for path in port.required_artifacts} <= quoted
        assert observation["admissionId"] == self.goal["admissionId"]
        assert [row["id"] for row in observation["criteria"]] == self.goal["criterionIds"]
        assert [row["slug"] for row in observation["members"]] == [row["slug"] for row in self.goal["members"]]
        historical = next(row for row in observation["members"] if row["slug"] == "historical-member")
        assert historical["proofProfile"] == "legacy-read-compatible"

    @unittest.skipUnless(os.name == "posix", "POSIX native-owner refusal contract")
    def test_posix_native_apply_refuses_without_source_move_or_receipts(self):
        _request, arguments = self.flat.legacy_request()
        before = self.flat.canonical_images()
        source_identity = self.flat.source.stat().st_dev, self.flat.source.stat().st_ino
        archive = self.flat.root / "work-items/archive/2026-10" / self.flat.slug
        for extra in ([], ["--inject-failure-at", "after-board"]):
            with self.subTest(extra=extra):
                result = subprocess.run(
                    [sys.executable, "-B", str(MUTATOR), *arguments, "--apply", *extra],
                    text=True, capture_output=True, timeout=240, check=False,
                )
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("WI-LEGACY-COMPLETION-NATIVE-UNSUPPORTED", result.stdout + result.stderr)
                self.assertEqual(self.flat.canonical_images(), before)
                self.assertEqual(
                    (self.flat.source.stat().st_dev, self.flat.source.stat().st_ino), source_identity
                )
                self.assertFalse(archive.exists())
                self.assertFalse((self.flat.root / ".scratch/work-items/legacy-flat-terminal").exists())

    @unittest.skipUnless(os.name == "nt", "native creator-bound flat close is Windows-only")
    def test_public_original_history_absence_uses_real_owner_and_both_receipts(self):
        self.complete_flat()
        result, observation = self.public_observation()
        self.assertEqual(result.returncode, 0, observation)
        self.assert_flat_credit(observation)

    @unittest.skipUnless(os.name == "nt", "native creator-bound flat close is Windows-only")
    def test_public_present_original_settled_history_keeps_raw_bytes_and_authority(self):
        self.complete_flat(history=True)
        before = self.owner.observe_work_item_terminal(self.roots["B"], f"work-item:{self.flat.slug}")
        raw = {path: path.read_bytes() for path in before.required_artifacts}
        result, observation = self.public_observation()
        self.assertEqual(result.returncode, 0, observation)
        self.assert_flat_credit(observation)
        self.assertEqual(raw, {path: path.read_bytes() for path in before.required_artifacts})
        after = self.owner.observe_work_item_terminal(self.roots["B"], f"work-item:{self.flat.slug}")
        before.verify(); after.verify()
        self.assertEqual(before.logical_reference, after.logical_reference)
        self.assertEqual(before.actual_location, after.actual_location)
        self.assertEqual(before.history_observation.selection, after.history_observation.selection)
        self.assertEqual(before.history_observation.ledger_sha256, after.history_observation.ledger_sha256)
        first, second = before.history_observation.authority_by_raw_line, after.history_observation.authority_by_raw_line
        self.assertEqual(set(first), set(second))
        for ordinal in first:
            self.assertEqual(first[ordinal].__dataclass_fields__.keys(), second[ordinal].__dataclass_fields__.keys())
            for field in first[ordinal].__dataclass_fields__:
                self.assertEqual(getattr(first[ordinal], field), getattr(second[ordinal], field), (ordinal, field))

    @unittest.skipUnless(os.name == "nt", "native creator-bound flat close is Windows-only")
    def test_pending_owner_is_not_goal_credit(self):
        self.complete_flat(pending=True)
        result, observation = self.public_observation()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(observation["decision"], "unverified")
        self.assertTrue(any("PENDING" in cause["detail"] for cause in observation["causes"]), observation)
        self.assertFalse(any(row["slug"] == self.flat.slug for row in observation["members"]))

    @unittest.skipUnless(os.name == "nt", "native creator-bound flat close is Windows-only")
    def test_pending_receipts_and_useful_outcome_refuse(self):
        self.complete_flat()
        original_receipt, original_acceptance = copy.deepcopy(self.flat_row["receipt"]), copy.deepcopy(self.flat_row["acceptance"])
        bug = self.archive / self.owner.BUG_DISPOSITIONS_RECEIPT
        self.flat_row["receipt"] = {"rootId": "B", "workItem": self.flat.slug, "path": bug.name,
                                    "sha256": hashlib.sha256(bug.read_bytes()).hexdigest()}
        self.record = self.write_goal(terminal=True)
        _process, result = self.public_observation()
        self.assertTrue(any(cause["code"] == "GC-RECEIPT" and cause["item"] == self.flat.slug
                            for cause in result["causes"]), result)
        self.assertFalse(any(row["slug"] == self.flat.slug for row in result["members"]))
        self.flat_row["receipt"] = original_receipt
        self.flat_row["acceptance"] = None
        self.record = self.write_goal(terminal=True)
        _process, result = self.public_observation()
        self.assertTrue(any(cause["code"] == "GC-OUTCOME" for cause in result["causes"]), result)
        self.assertNotEqual(result["decision"], "eligible")
        self.flat_row["acceptance"] = original_acceptance
        self.record = self.write_goal(terminal=True)
        for name in (self.owner.LEGACY_COMPLETION_RECEIPT, self.owner.BUG_DISPOSITIONS_RECEIPT):
            path = self.archive / name
            saved = self.flat.root / f"fixture-held-{name}"
            raw = path.read_bytes(); path.rename(saved)
            try:
                process, result = self.public_observation()
                self.assertEqual(process.returncode, 1)
                self.assertEqual(result["decision"], "unverified")
                self.assertTrue(result["causes"])
                self.assertFalse(any(row["slug"] == self.flat.slug for row in result["members"]))
                self.assertEqual(saved.read_bytes(), raw)
            finally:
                saved.rename(path)

    @unittest.skipUnless(os.name == "nt", "native creator-bound flat close is Windows-only")
    def test_held_native_drift_and_new_ambiguity_refuse(self):
        self.complete_flat()
        self.checker.load_lifecycle_owner = lambda: self.owner
        original_observe = self.owner.observe_work_item_terminal
        original_verify = self.owner.WorkItemTerminalObservation.verify
        held = []
        def observe(root, reference, **kwargs):
            value = original_observe(root, reference, **kwargs)
            if reference == f"work-item:{self.flat.slug}": held.append(value)
            return value
        calls = []
        moved = self.flat.root / "fixture-held-required-proof.bin"
        replacement = []
        def verify(value):
            if held and value is held[-1]:
                calls.append(value)
                if len(calls) == 2:
                    path = next(path for path in value.required_artifacts if path.name == "proof.md")
                    raw = path.read_bytes(); path.rename(moved); path.write_bytes(raw)
                    replacement.append(path)
                    self.assertNotEqual(self.owner._lifecycle_file_identity(path.lstat()),
                                        self.owner._lifecycle_file_identity(moved.lstat()))
            return original_verify(value)
        self.owner.observe_work_item_terminal = observe
        self.owner.WorkItemTerminalObservation.verify = verify
        try:
            result = self.checker.evaluate_goal_completion(self.roots["A"], self.record, phase="final")
        finally:
            self.owner.observe_work_item_terminal = original_observe
            self.owner.WorkItemTerminalObservation.verify = original_verify
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["decision"], "unverified")
        self.assertTrue(any(cause["code"] == "GC-DRIFT" and cause["item"] == self.flat.slug for cause in result["causes"]), result)
        self.assertFalse(any(row["slug"] == self.flat.slug for row in result["members"]))
        # Reconcile only fixture-owned replacement; product never removed it.
        replacement[0].rename(self.flat.root / "fixture-preserved-replacement.bin")
        moved.rename(replacement[0])
        duplicate = self.flat.root / "work-items/backlog" / f"{self.flat.slug}.md"
        duplicate.write_bytes((self.archive / "legacy-source" / duplicate.name).read_bytes())
        try:
            process, ambiguous = self.public_observation()
            self.assertEqual(process.returncode, 1)
            self.assertEqual(ambiguous["decision"], "unverified")
            self.assertTrue(any("LOCATION" in cause["detail"] or "ambiguous" in cause["detail"]
                                for cause in ambiguous["causes"]), ambiguous)
        finally:
            duplicate.rename(self.flat.root / "fixture-preserved-duplicate.md")


def test_goal_progress_preclose_and_owner_closed_final_are_distinct(tmp_path: Path):
    checker, owner, roots, goal, write_goal, close_member = _goal_fixture(tmp_path)
    close_member("A", "a")
    record = write_goal()
    progress = checker.evaluate_goal_completion(roots["A"], record)
    assert progress["decision"] == "continue"
    assert next(row for row in progress["roots"] if row["id"] == "B")["active"] == ["b"]
    close_member("B", "b")
    for row in goal["criteria"][:2]:
        row["state"] = "pending"
    goal["criteria"][1]["actions"] = [{"id": "last-close", "kind": "item-close", "rootId": "A", "item": "g", "state": "pending", "evidence": None}]
    record = write_goal()
    snapshot = {str(path): path.read_bytes() for root in roots.values() for path in root.rglob("*") if path.is_file()}
    assert checker.evaluate_goal_completion(roots["A"], record, phase="preclose")["decision"] == "ready-for-last-close"
    assert checker.evaluate_goal_completion(roots["A"], record, phase="final")["decision"] == "continue"
    assert snapshot == {str(path): path.read_bytes() for root in roots.values() for path in root.rglob("*") if path.is_file()}
    close_member("A", "g")
    for row in goal["criteria"]:
        row["state"] = "verified"
        row["actions"] = []
    record = write_goal(terminal=True)
    final = checker.evaluate_goal_completion(roots["A"], record, phase="final")
    assert final["decision"] == "eligible", final
    assert [row["id"] for row in final["criteria"]] == ["alpha", "omega", "useful"]
    assert all(row["state"] == "delivered-closed" and row["proofProfile"] == "modern" for row in final["members"])


def test_goal_equal_readme_with_unbound_archive_is_not_completion(tmp_path: Path):
    checker, owner, roots, goal, write_goal, close_member = _goal_fixture(tmp_path)
    for rid, slug in (("A", "a"), ("B", "b"), ("A", "g")):
        close_member(rid, slug)
    unknown = roots["B"] / "work-items" / "archive" / "2026-07" / "unknown"
    unknown.mkdir(parents=True)
    (unknown / "leaf.any").write_bytes(b"CLOSED without admitted authority")
    record = write_goal(terminal=True)
    assert owner.observe_readme(roots["B"])["matches"] is True
    before = {str(path): path.read_bytes() for root in roots.values() for path in root.rglob("*") if path.is_file()}
    result = checker.evaluate_goal_completion(roots["A"], record, phase="final")
    assert result["decision"] == "unverified", result
    assert any(row["code"] == "GC-REFERENCE" and "WI-ARCHIVE-ENTITY-UNBOUND" in row["detail"] for row in result["causes"]), result
    assert before == {str(path): path.read_bytes() for root in roots.values() for path in root.rglob("*") if path.is_file()}


def test_goal_direct_archive_metadata_keeps_real_receiving_and_pending_guards(tmp_path: Path):
    checker, owner, roots, goal, write_goal, close_member = _goal_fixture(tmp_path)
    for rid, slug in (("A", "a"), ("B", "b"), ("A", "g")):
        close_member(rid, slug)
    record = write_goal(terminal=True)
    assert checker.evaluate_goal_completion(roots["A"], record, phase="final")["decision"] == "eligible"
    metadata = roots["A"] / "work-items" / "archive" / "2026-10" / "arbitrary-metadata"
    metadata.write_bytes(b"\xff\x00non-authorizing")
    record = write_goal(terminal=True)
    def receive():
        result = subprocess.run([sys.executable, "-B", str(CHECKER), "--root", str(roots["A"]),
            "--goal", str(record), "--goal-phase", "final", "--json"], text=True, capture_output=True, timeout=30)
        return result, json.loads(result.stdout)
    result, wire = receive()
    assert result.returncode == 0 and wire["decision"] == "eligible", wire
    assert owner.observe_readme(roots["A"])["archiveInventory"] == {
        "schemaVersion": 1, "acquisitionComplete": True, "classificationComplete": True, "unbound": []}
    goal["criteria"][-1]["state"] = "pending"
    record = write_goal(terminal=True)
    result, wire = receive()
    assert result.returncode == 1 and wire["decision"] != "eligible", wire
    goal["criteria"][-1]["state"] = "verified"
    unknown = roots["B"] / "work-items" / "archive" / "2026-07" / "unknown"
    unknown.mkdir(parents=True)
    (unknown / "leaf").write_bytes(b"unbound data")
    record = write_goal(terminal=True)
    result, wire = receive()
    assert result.returncode == 1 and wire["decision"] == "unverified", wire
    assert any(row["code"] == "GC-REFERENCE" for row in wire["causes"])
    assert metadata.read_bytes() == b"\xff\x00non-authorizing"


def test_goal_archive_inventory_missing_and_illtyped_are_not_inferred_clean():
    checker = load_checker_module()
    valid = {"schemaVersion": 1, "acquisitionComplete": True, "classificationComplete": True, "unbound": []}
    checker._require_complete_archive_inventory({"archiveInventory": valid}, "root-id")
    for value in (None, {}, {**valid, "schemaVersion": True}, {**valid, "acquisitionComplete": None},
                  {**valid, "classificationComplete": False}, {**valid, "unbound": None}):
        try:
            checker._require_complete_archive_inventory({"archiveInventory": value}, "root-id")
        except checker.GoalInputError as error:
            assert error.code == "GC-REFERENCE" and "WI-ARCHIVE-ENTITY-UNBOUND" in str(error)
        else:
            raise AssertionError(f"invalid observation admitted: {value}")


def test_goal_original_projection_cannot_be_reduced(tmp_path: Path):
    checker, _owner, roots, goal, write_goal, _close = _goal_fixture(tmp_path)
    original = copy.deepcopy(goal)
    for mode in ("criterion", "root", "member"):
        goal.clear()
        goal.update(copy.deepcopy(original))
        if mode == "criterion":
            goal["criterionIds"].pop()
            goal["criteria"].pop()
        elif mode == "root":
            goal["roots"].pop()
            goal["members"] = [row for row in goal["members"] if row["rootId"] != "B"]
        else:
            goal["members"].pop()
        observation = checker.evaluate_goal_completion(roots["A"], write_goal(), phase="final")
        assert observation["decision"] == "unverified"
        assert any(row["code"] == "GC-SCOPE" for row in observation["causes"]), mode


def test_goal_required_proof_and_reference_drift_remain_visible(tmp_path: Path):
    checker, _owner, roots, goal, write_goal, close_member = _goal_fixture(tmp_path)
    for rid, slug in (("A", "a"), ("B", "b"), ("A", "g")):
        close_member(rid, slug)
    record = write_goal(terminal=True)
    receipt = goal["members"][0]["receipt"]
    goal["members"][0]["receipt"] = None
    observation = checker.evaluate_goal_completion(roots["A"], write_goal(terminal=True), phase="final")
    assert any(row["code"] == "GC-RECEIPT" for row in observation["causes"])
    goal["members"][0]["receipt"] = receipt
    (roots["A"] / "inputs" / "source.md").write_text("Changed pinned source.\n", encoding="utf-8")
    observation = checker.evaluate_goal_completion(roots["A"], record, phase="final")
    assert observation["decision"] == "unverified"
    assert any(row["code"] == "GC-DRIFT" and row["ref"] is not None for row in observation["causes"])


def test_goal_cli_requires_explicit_scope_and_preserves_default_route(tmp_path: Path):
    for args in (("--goal", "epic.md", "--json"), ("--root", str(tmp_path), "--goal", "epic.md", "--json", "--active-only")):
        result = subprocess.run([sys.executable, "-B", str(CHECKER), *args], capture_output=True, text=True, timeout=30)
        assert result.returncode != 0 and "error:" in result.stderr
    item = write_staged_item(tmp_path)
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "valid state only, NOT completion" in result.stdout and item.name in result.stdout


def test_goal_legacy_receipt_applicability_and_variable_criteria(tmp_path: Path):
    checker, owner, roots, goal, write_goal, close_member = _goal_fixture(tmp_path, criterion_ids=("scope", "settlement"), legacy=True)
    for rid, slug in (("A", "a"), ("B", "b"), ("A", "g")):
        close_member(rid, slug)
    record = write_goal(terminal=True)
    observation = checker.evaluate_goal_completion(roots["A"], record, phase="final")
    assert observation["decision"] == "eligible", observation
    legacy = next(row for row in observation["members"] if row["slug"] == "historical-member")
    assert legacy["proofProfile"] == "legacy-read-compatible" and legacy["state"] == "delivered-closed"
    assert [row["id"] for row in observation["criteria"]] == ["scope", "settlement"]
    historical = roots["A"] / "work-items/archive/2026-06/historical-member/closure.md"
    historical.write_bytes(historical.read_bytes() + b"Lifecycle-schema: work-items-physical-v1\n")
    record = write_goal(terminal=True)
    assert owner.observe_readme(roots["A"])["matches"] is True
    rejected = checker.evaluate_goal_completion(roots["A"], record, phase="final")
    assert rejected["decision"] == "unverified", rejected
    assert any(row["code"] == "GC-REFERENCE" and "input-role=strict" in row["detail"]
        and "work-items/archive/2026-06/historical-member/status.md" in row["detail"]
        for row in rejected["causes"]), rejected
    assert not any(row.get("slug") == "historical-member" and row.get("proofProfile") == "modern"
        for row in rejected["members"])


def test_goal_invalid_bindings_and_pending_duties_cannot_become_eligible(tmp_path: Path):
    checker, _owner, roots, goal, write_goal, close_member = _goal_fixture(tmp_path)
    for rid, slug in (("A", "a"), ("B", "b"), ("A", "g")):
        close_member(rid, slug)
    original = copy.deepcopy(goal)
    for mode, expected_code in (("version", "GC-SCOPE"), ("identity", "GC-SCOPE"),
                                ("missing-root", "GC-REFERENCE"), ("escape", "GC-REFERENCE"),
                                ("coverage", "GC-CRITERION"), ("resource", "GC-CRITERION")):
        goal.clear()
        goal.update(copy.deepcopy(original))
        if mode == "version":
            goal["version"] = 2
        elif mode == "identity":
            goal["roots"][1]["locator"] = goal["roots"][0]["locator"]
            goal["roots"][1]["identity"] = goal["roots"][0]["identity"]
        elif mode == "missing-root":
            missing = tmp_path / "unavailable"
            goal["roots"][1]["locator"] = goal["roots"][1]["identity"] = str(missing.resolve())
        elif mode == "escape":
            goal["coverage"]["audit"]["path"] = "../outside.md"
        elif mode == "coverage":
            goal["coverage"]["pending"] = ["original-unchecked-variant"]
        else:
            goal["criteria"][1]["actions"] = [{"id": "resource-teardown", "kind": "resource", "rootId": "A", "item": "g", "state": "pending", "evidence": None}]
        observation = checker.evaluate_goal_completion(roots["A"], write_goal(terminal=True), phase="final")
        assert observation["decision"] != "eligible", mode
        assert any(row["code"] == expected_code for row in observation["causes"]), (mode, observation)


def test_goal_admission_amendment_is_additive_and_retains_discovered_member(tmp_path: Path):
    checker, owner, roots, goal, write_goal, _close = _goal_fixture(tmp_path)
    root = roots["A"]
    brief = root / "inputs" / "brief.md"
    original_bytes = brief.read_bytes()
    previous = root / "inputs" / "brief-v1.md"
    previous.write_bytes(original_bytes)
    validator = checker.load_validator()
    admission, prefix = checker._goal_block(original_bytes, "admission", validator)
    owner.create_candidate(root, "c", b"Task: Discovered scope.\nNext action: Start.\nupdated: 2026-10-08T00:00:00Z\n")
    owner.start_item(root, "c", (root / "work-items" / "active" / "g" / "status.md").read_bytes())
    admission["revision"] = 2
    admission["previousAdmission"] = {"rootId": "A", "workItem": None, "path": "inputs/brief-v1.md", "sha256": hashlib.sha256(original_bytes).hexdigest()}
    admission["amendment"] = copy.deepcopy(goal["criteria"][0]["acceptance"])
    admission["criterionIds"].append("added-duty")
    admission["originalMembers"].append({"rootId": "A", "slug": "c"})
    goal["criterionIds"] = admission["criterionIds"][:]
    added = copy.deepcopy(goal["criteria"][0])
    added["id"] = "added-duty"
    goal["criteria"].append(added)
    goal["members"].append({"rootId": "A", "slug": "c", "outcome": "pending", "acceptance": None, "receipt": None})
    def update_admission():
        brief.write_bytes(prefix + b"<!-- orchestrarium-goal-admission:v1 -->\n" + json.dumps(admission).encode()
                          + b"\n<!-- /orchestrarium-goal-admission:v1 -->\n")
        goal["admission"]["sha256"] = hashlib.sha256(brief.read_bytes()).hexdigest()
    update_admission()
    observation = checker.evaluate_goal_completion(root, write_goal())
    assert observation["decision"] == "continue", observation
    assert any(row["slug"] == "c" for row in observation["members"])
    admission["criterionIds"].remove("useful")
    goal["criterionIds"].remove("useful")
    goal["criteria"] = [row for row in goal["criteria"] if row["id"] != "useful"]
    update_admission()
    refused = checker.evaluate_goal_completion(root, write_goal())
    assert refused["decision"] == "unverified"
    assert any(row["code"] == "GC-SCOPE" for row in refused["causes"])


def test_goal_preservation_root_retains_identity_and_authority_without_task_artifacts(tmp_path: Path):
    checker, _owner, roots, goal, write_goal, close_member = _goal_fixture(tmp_path, preservation=True)
    close_member("A", "a")
    before = {str(p): p.read_bytes() if p.is_file() else None for p in roots["B"].rglob("*")}
    observation = checker.evaluate_goal_completion(roots["A"], write_goal())
    assert observation["decision"] == "continue", observation
    assert [row["id"] for row in observation["roots"]] == ["A", "B"]
    assert observation["roots"][1] == {"id": "B", "identity": str(roots["B"].resolve()), "active": [], "taskDomain": "preservation-only"}
    assert before == {str(p): p.read_bytes() if p.is_file() else None for p in roots["B"].rglob("*")}
    assert not (roots["B"] / "work-items").exists() and not (roots["B"] / ".scratch").exists()
    close_member("A", "g")
    record = write_goal(terminal=True)
    result = subprocess.run([sys.executable, "-B", str(CHECKER), "--root", str(roots["A"]), "--goal", str(record),
                             "--goal-phase", "final", "--json"], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["decision"] == "eligible"


def test_goal_taskless_domain_expectations_and_recheck_are_not_missing_equals_empty(tmp_path: Path):
    checker, owner, roots, goal, write_goal, _close = _goal_fixture(tmp_path, preservation=True)
    original = copy.deepcopy(goal)
    for mode in ("item-action", "task-ref", "file-domain"):
        goal.clear()
        goal.update(copy.deepcopy(original))
        if mode == "item-action":
            goal["criteria"][0]["actions"] = [{"id": "B-close", "kind": "item-close", "rootId": "B", "item": "b", "state": "pending", "evidence": None}]
        elif mode == "task-ref":
            goal["criteria"][0]["sourcePins"] = [{"rootId": "B", "workItem": None, "path": "work-items/status.md", "sha256": "0" * 64}]
        else:
            (roots["B"] / "work-items").write_bytes(b"Not a directory.\n")
        result = checker.evaluate_goal_completion(roots["A"], write_goal())
        assert result["decision"] == "unverified", mode
        assert any(row["code"] == "GC-REFERENCE" for row in result["causes"]), result
    (roots["B"] / "work-items").unlink()
    goal.clear()
    goal.update(copy.deepcopy(original))
    original_profile = checker._goal_root_profile
    counts = {"B": 0}
    def acquire_then_appear(*args, **kwargs):
        result = original_profile(*args, **kwargs)
        if args[1] == "B":
            counts["B"] += 1
            if counts["B"] == 1:
                (roots["B"] / "work-items").mkdir()
        return result
    checker._goal_root_profile = acquire_then_appear
    observed = checker.evaluate_goal_completion(roots["A"], write_goal())
    assert observed["decision"] == "unverified"
    assert any(row["code"] == "GC-DRIFT" for row in observed["causes"]), observed
    assert observed["roots"][1]["taskDomain"] == "unverified"


def _rewrite_goal_admission(checker, root, goal, update):
    brief = root / "inputs" / "brief.md"
    value, prefix = checker._goal_block(brief.read_bytes(), "admission", checker.load_validator())
    update(value)
    brief.write_bytes(prefix + b"<!-- orchestrarium-goal-admission:v1 -->\n" + json.dumps(value).encode()
                      + b"\n<!-- /orchestrarium-goal-admission:v1 -->\n")
    goal["admission"]["sha256"] = hashlib.sha256(brief.read_bytes()).hexdigest()


def test_goal_unresolved_managed_authority_cannot_complete(tmp_path: Path):
    checker, _owner, roots, goal, write_goal, close_member = _goal_fixture(tmp_path)
    for rid, slug in (("A", "a"), ("B", "b"), ("A", "g")):
        close_member(rid, slug)
    authority = copy.deepcopy(goal["roots"][1]["admission"])
    _rewrite_goal_admission(checker, roots["A"], goal,
        lambda admission: admission["unresolvedRoots"].append({"id": "B", "authority": authority}))
    result = checker.evaluate_goal_completion(roots["A"], write_goal(terminal=True), phase="final")
    assert result["decision"] == "unverified", result
    assert any(row["code"] == "GC-SCOPE" and row["rootId"] == "B" for row in result["causes"])


def test_goal_null_rules_admit_only_pending_coordinator_close_and_preserve_proof_requirements(tmp_path: Path):
    checker, _owner, roots, goal, write_goal, close_member = _goal_fixture(tmp_path)
    close_member("A", "a")
    close_member("B", "b")
    goal["rules"] = {"emptyActiveCriterion": None, "settlementCriterion": None}
    _rewrite_goal_admission(checker, roots["A"], goal, lambda admission: admission.update(rules=goal["rules"]))
    last_close = {"id": "last-close", "kind": "item-close", "rootId": "A", "item": "g", "state": "pending", "evidence": None}
    goal["criteria"][0]["actions"] = [last_close]
    record = write_goal()
    observed = checker.evaluate_goal_completion(roots["A"], record, phase="preclose")
    assert observed["decision"] == "ready-for-last-close", observed
    assert observed["criteria"][0]["state"] == "pending"  # Pending action remains visible.
    assert checker.evaluate_goal_completion(roots["A"], record, phase="final")["decision"] != "eligible"
    goal["criteria"][0]["actions"] = []
    assert checker.evaluate_goal_completion(roots["A"], write_goal(), phase="preclose")["decision"] == "ready-for-last-close"
    for kind in ("check", "git", "resource"):
        other = dict(last_close, id=kind, kind=kind)
        goal["criteria"][0]["actions"] = [last_close, other]
        assert checker.evaluate_goal_completion(roots["A"], write_goal(), phase="preclose")["decision"] == "continue", kind
    goal["criteria"][0]["actions"] = [last_close]
    goal["criteria"][0]["acceptance"] = None
    missing = checker.evaluate_goal_completion(roots["A"], write_goal(), phase="preclose")
    assert missing["decision"] == "unverified" and any(row["code"] == "GC-CRITERION" for row in missing["causes"])


REQUIRED_SENTINEL_STUB = """\
def resolve_epic_locations(epics_dir, slug):
    return {"state": "missing", "locations": []}
"""


def test_checker_fails_when_required_sentinel_candidates_are_missing_without_epic_link(
    tmp_path: Path,
):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle")
    write_valid_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.count("required-sentinel-dependency-unavailable") == 1
    assert "installed-sibling" in result.stdout
    assert "source-universal-hooks" in result.stdout
    assert "RESULT: FAIL" in result.stdout


def test_checker_preserves_required_sentinel_import_failure_cause(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", "def broken(:\n")
    write_valid_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.count("required-sentinel-dependency-unavailable") == 1
    assert "installed-sibling: SyntaxError:" in result.stdout
    assert "invalid syntax" in result.stdout


def test_checker_rejects_incomplete_required_sentinel_contract(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(
        tmp_path / "bundle",
        "def unrelated_capability():\n    return None\n",
    )
    write_valid_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert result.stdout.count("required-sentinel-contract-mismatch") == 1
    assert "missing callable(s): resolve_epic_locations" in result.stdout


def test_checker_keeps_absent_optional_sentinel_reporting_verdict_neutral(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    write_valid_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout
    assert "required-sentinel-" not in result.stdout
    assert "sentinel optional reporting unavailable: missing callable(s):" in result.stdout
    assert "build_context" in result.stdout
    assert "evaluate_all" in result.stdout


def test_checker_accepts_minimal_staged_status_and_reports_v1_next_action(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    write_staged_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS staged-item" in result.stdout
    assert "staged-item -- Next action: Run the staged checker gate." in result.stdout
    assert "status.md missing section" not in result.stdout


def test_checker_accepts_asterisk_bullet_staged_status_fields(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    status = minimal_staged_status()
    for field in (
        "Task",
        "Current step",
        "Last result",
        "Next action",
        "Scope boundary",
        "Owner",
        "Integration owner",
        "Evidence gate",
    ):
        status = status.replace(f"{field}: ", f"* {field}: ")
    write_staged_item(repo, status=status)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS staged-item" in result.stdout
    assert "staged-item -- Next action: Run the staged checker gate." in result.stdout


def test_checker_rejects_staged_status_missing_required_v1_field(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    status = minimal_staged_status()
    status = status.replace(
        "Evidence gate: Focused and full lifecycle suites.\n",
        "",
    )
    write_staged_item(repo, status=status)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "staged status missing fields: evidence gate" in result.stdout
    assert "status.md missing section" not in result.stdout


def test_checker_preserves_open_revise_failure_on_staged_status(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    revise = ledger_event(
        schemaVersion=2,
        runId="run-staged-revise-001",
        workItem="staged-item",
        status="revise",
        gate="REVISE",
        eventKind="standalone",
        lane="staged-contract",
        effort="high",
        findingClass="correctness",
    )
    write_staged_item(repo, event=revise)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "open REVISE obligation: run-staged-revise-001" in result.stdout
    assert "status.md missing section" not in result.stdout


def test_checker_preserves_unsettled_launch_failure_on_staged_status(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(tmp_path / "bundle", REQUIRED_SENTINEL_STUB)
    launch = ledger_event(
        schemaVersion=2,
        runId="run-staged-launch-001",
        workItem="staged-item",
        status="running",
        gate="none",
        eventKind="launch",
        lane="staged-contract",
        effort="high",
        startedAt="2026-07-31T10:00:00Z",
        updatedAt="2026-07-31T10:05:00Z",
    )
    write_staged_item(repo, event=launch)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "unsettled launch: run-staged-launch-001" in result.stdout
    assert "status.md missing section" not in result.stdout


def test_checker_keeps_failing_optional_sentinel_reporting_verdict_neutral(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(
        tmp_path / "bundle",
        REQUIRED_SENTINEL_STUB
        + """
def build_context(root):
    return {"root": root}

def evaluate_all(context):
    raise RuntimeError("optional reporting failed")
""",
    )
    write_valid_item(repo)

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout
    assert "required-sentinel-" not in result.stdout
    assert (
        "sentinel optional reporting failed: RuntimeError: optional reporting failed"
        in result.stdout
    )


def test_checker_preserves_required_epic_resolver_call_failure_cause(tmp_path: Path):
    repo = tmp_path / "repo"
    checker = write_checker_bundle(
        tmp_path / "bundle",
        REQUIRED_SENTINEL_STUB.replace(
            'return {"state": "missing", "locations": []}',
            'raise RuntimeError("epic resolution failed")',
        ),
    )
    item = write_valid_item(repo)
    (item / "status.md").write_text(
        valid_status().replace(
            "**Primary task status**: open",
            "**Primary task status**: open\n**Epic**: demo-epic",
        ),
        encoding="utf-8",
    )

    result = run_bundled_checker(checker, repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "epic location resolver failed: RuntimeError: epic resolution failed" in result.stdout


def test_checker_treats_unowned_markdown_sections_as_inert(tmp_path: Path):
    item = write_valid_item(tmp_path)
    baseline = run_checker(tmp_path)
    with (item / "status.md").open("a", encoding="utf-8") as handle:
        handle.write(
            "\n## Delivery action\n\n"
            "This retired heading is ordinary Markdown and carries no control meaning.\n"
        )

    with_unowned_section = run_checker(tmp_path)

    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    assert with_unowned_section.returncode == baseline.returncode
    assert with_unowned_section.stdout == baseline.stdout
    assert with_unowned_section.stderr == baseline.stderr


def test_checker_passes_when_no_active_directory_exists(tmp_path: Path):
    result = run_checker(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "no active work-items" in result.stdout

    repo = tmp_path / "known-empty-base"
    work_items = repo / "work-items"
    work_items.mkdir(parents=True)
    owner = load_checker_module().load_lifecycle_owner()
    before = list(work_items.iterdir())
    base, selected, evidence = owner.project_root_identity(work_items, known_work_items_root=work_items)
    assert (base, selected) == (repo, work_items)
    assert list(work_items.iterdir()) == before and not (repo / ".scratch").exists()
    for alias, active in ((repo, "work-items/active"), (work_items, "active")):
        checked = run_checker(alias, "--active-dir", active)
        assert checked.returncode == 0, checked.stdout + checked.stderr
        assert "no active work-items" in checked.stdout
        assert not (work_items / ".scratch").exists()
    assert (repo / ".scratch" / "work-items-lifecycle-owner.lock").is_file()


def test_checker_validates_all_active_items(tmp_path: Path):
    write_valid_item(tmp_path, "valid-item")
    bad = tmp_path / "work-items" / "active" / "bad-item"
    bad.mkdir(parents=True)
    (bad / "status.md").write_text(valid_status(), encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "PASS valid-item" in result.stdout
    assert "FAIL bad-item" in result.stdout
    assert "cannot read ledger" in result.stdout
    assert "ledger has no events" not in result.stdout


def test_checker_rejects_unapplied_active_bug_disposition_manifest(
    tmp_path: Path,
) -> None:
    item = write_valid_item(tmp_path)
    (item / "bug-dispositions.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "workItem": item.name,
                "closedAt": "2026-08-11T10:09:00Z",
                "bugs": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "WI-BUG-DISPOSITIONS-PENDING" in result.stdout


def test_pass_surfaces_active_items_and_denies_completion(tmp_path: Path):
    """Forcing function (bug 2026-07-18-false-completion-claim-validator-pass-conflated-with-done):
    a green RESULT must never read as 'all closed'. The checker prints every active item + its
    Next action, and the RESULT line itself says valid-state-not-completion — so a PASS cannot be
    quoted as completion while active work remains."""
    write_valid_item(tmp_path, "active-item")
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "STILL OPEN" in result.stdout
    assert "active-item -- Next action: Continue." in result.stdout
    assert "NOT completion" in result.stdout
    # and the empty case must not claim completion falsely either — it says 'no active work-items'
    empty = run_checker(tmp_path / "does-not-exist")
    assert "no active work-items" in empty.stdout
    assert "STILL OPEN" not in empty.stdout  # no items => no STILL OPEN block


def test_forcing_function_survives_non_ascii_next_action_on_narrow_console(tmp_path: Path):
    """The enumeration prints ARBITRARY status content; a non-ASCII Next action (em-dash,
    arrow) must NOT crash the report on a non-UTF-8 console. The stream-level errors=replace
    guard in main() owns this — replacing the em-dash in one string literal would not
    (fable + codex ff-review: the crash class lives in the interpolated data)."""
    item = write_valid_item(tmp_path, "unicode-item")
    (item / "status.md").write_text(
        valid_status().replace("Continue.", "Run probe 1 — then reconcile → close."),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONIOENCODING": "cp866"}
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(tmp_path)],
        text=True, capture_output=True, encoding="cp866", errors="replace", env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr  # no UnicodeEncodeError
    assert "unicode-item" in result.stdout
    assert "STILL OPEN" in result.stdout


def test_next_actionable_heading_does_not_false_match(tmp_path: Path):
    """Exact heading match: a '## Next actionable' section must NOT be read as the
    '## Next action' section (codex ff-review — the old startswith accepted it)."""
    item = write_valid_item(tmp_path, "actionable-item")
    (item / "status.md").write_text(
        "# Status\nstatus: active\n\n## Current state\n**Primary task status**: open\n\n"
        "## Active agents\n- none\n\n## Completed agents\n- none\n\n"
        "## Next actionable\nWRONG heading content\n\n"
        "## Next action\nCORRECT action content\n",
        encoding="utf-8",
    )
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "CORRECT action content" in result.stdout
    assert "WRONG heading content" not in result.stdout


def status_with_depends(dep_value: str) -> str:
    return valid_status().replace(
        "**Primary task status**: open",
        "**Primary task status**: open\n**Depends-on**: " + dep_value,
    )


def status_with_epic(epic_value: str) -> str:
    return valid_status().replace(
        "**Primary task status**: open",
        "**Primary task status**: open\n**Epic**: " + epic_value,
    )


def status_with_no_epic_rationale() -> str:
    return valid_status().replace(
        "**Primary task status**: open",
        "**Primary task status**: open\n**No-epic rationale**: standalone fixes",
    )


def write_item_with_status(root: Path, name: str, status_text: str) -> Path:
    item = root / "work-items" / "active" / name
    (item / "reviews").mkdir(parents=True)
    (item / "status.md").write_text(status_text, encoding="utf-8")
    (item / "reviews" / "qa.md").write_text("PASS\n", encoding="utf-8")
    (item / "agent-runs.jsonl").write_text(json.dumps(ledger_event(workItem=name)) + "\n", encoding="utf-8")
    return item


def test_relation_slug_validation_consumes_canonical_lifecycle_owner(tmp_path: Path):
    checker = load_checker_module()
    lifecycle = checker.load_lifecycle_owner()
    slug_is_valid = getattr(lifecycle, "is_valid_slug", None)
    assert callable(slug_is_valid), "lifecycle owner must publish its canonical slug predicate"
    sentinels = checker.load_required_sentinels()
    assert callable(sentinels.resolve_epic_locations), sentinels.diagnostic()

    matrix = (
        ("legacy-valid-slug", True),
        ("2026-07-19-model-ranking-aa-coding-index-v1.1", True),
        ("trailing.", False),
        ("double..dot", False),
        ("Uppercase", False),
        ("under_score", False),
        ("path/segment", False),
        ("../traversal", False),
    )
    for index, (slug, expected) in enumerate(matrix):
        try:
            lifecycle._validate_slug(slug)
        except lifecycle.LifecycleError as exc:
            assert exc.failure_id == "WI-INVALID-SLUG", slug
            mutator_accepts = False
        else:
            mutator_accepts = True
        assert mutator_accepts is expected, slug
        assert slug_is_valid(slug) is expected, slug

        case_root = tmp_path / f"case-{index}"
        status = valid_status().replace(
            "**Primary task status**: open",
            "**Primary task status**: open\n"
            f"**Depends-on**: {slug}\n"
            f"**Epic**: {slug}",
        )
        item = write_item_with_status(case_root, "relation-source", status)
        active_dir = case_root / "work-items" / "active"
        dependency_notes = checker.blocked_by_notes(
            item,
            case_root,
            lifecycle,
            slug_is_valid,
        )
        epic_notes = checker.epic_link_notes(
            item,
            active_dir,
            sentinels.resolve_epic_locations,
            slug_is_valid,
        )
        if expected:
            assert dependency_notes == [
                f"blocked-by: {slug} (unresolved Depends-on)",
                f"dangling Depends-on: {slug} (no matching work-item)"
            ], slug
            assert epic_notes and epic_notes[0].startswith(f"dangling Epic: {slug} "), slug
        else:
            assert dependency_notes == [f"invalid Depends-on: {slug}"], slug
            assert epic_notes == [f"invalid Epic: {slug}"], slug


# --- aging report (B2): informational, never a failure ----------------------

def test_aging_flags_old_item_as_info(tmp_path: Path):
    write_valid_item(tmp_path, "2026-01-01-old-item")
    result = run_checker(tmp_path, "--max-age-days", "30", "--now", "2026-06-13T00:00:00Z")
    assert result.returncode == 0, result.stdout  # aging is info, not a failure
    assert "PASS 2026-01-01-old-item" in result.stdout
    assert "info: aging" in result.stdout


def test_aging_not_flagged_for_recent_item(tmp_path: Path):
    write_valid_item(tmp_path, "2026-06-10-recent-item")
    result = run_checker(tmp_path, "--max-age-days", "30", "--now", "2026-06-13T00:00:00Z")
    assert result.returncode == 0
    assert "aging" not in result.stdout


def test_aging_disabled_by_default(tmp_path: Path):
    write_valid_item(tmp_path, "2026-01-01-old-item")
    result = run_checker(tmp_path)  # no --max-age-days -> default 0 -> disabled
    assert result.returncode == 0
    assert "aging" not in result.stdout


# --- blocker-state (B2): informational, never a failure ---------------------

def test_blocked_by_open_target_is_info_not_failure(tmp_path: Path):
    write_valid_item(tmp_path, "dep-target")  # exists, valid, not done
    write_item_with_status(tmp_path, "blocked-item", status_with_depends("dep-target"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout  # blocked is expected state, not a failure
    assert "info: blocked-by: dep-target" in result.stdout


def test_blocked_by_backlog_target_is_info_not_dangling(tmp_path: Path):
    backlog = tmp_path / "work-items" / "backlog"
    backlog.mkdir(parents=True)
    (backlog / "dep-target.md").write_text("status: candidate\n", encoding="utf-8")
    write_item_with_status(tmp_path, "blocked-item", status_with_depends("dep-target"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "info: blocked-by: dep-target (open Depends-on)" in result.stdout
    assert "dangling Depends-on: dep-target" not in result.stdout


def test_dangling_depends_on_reported(tmp_path: Path):
    write_item_with_status(tmp_path, "item-x", status_with_depends("ghost-item"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "blocked-by: ghost-item (unresolved Depends-on)" in result.stdout
    assert "dangling Depends-on: ghost-item" in result.stdout


def test_blocked_by_done_target_not_reported(tmp_path: Path):
    arch = tmp_path / "work-items" / "archive" / "2026-05" / "done-dep"
    arch.mkdir(parents=True)
    (arch / "status.md").write_text("State: closed\n", encoding="utf-8")
    (arch / "closure.md").write_text(
        "Closed: 2026-05-03T10:05:00Z\nOutcome: Delivered the synthetic dependency.\n"
        "Evidence: Accepted fixture result.\nResidual risk: None.\n", encoding="utf-8"
    )
    write_item_with_status(tmp_path, "item-y", status_with_depends("done-dep"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "blocked-by" not in result.stdout


def test_duplicate_dependency_location_fails_closed(tmp_path: Path):
    backlog = tmp_path / "work-items" / "backlog"
    backlog.mkdir(parents=True)
    (backlog / "dep-target.md").write_text("status: candidate\n", encoding="utf-8")
    write_valid_item(tmp_path, "dep-target")
    write_item_with_status(tmp_path, "blocked-item", status_with_depends("dep-target"))
    result = run_checker(tmp_path)
    assert result.returncode == 1, result.stdout
    assert "WI-CATEGORY-DUAL-LOCATION" in result.stdout
    assert "blocked-by: dep-target (unresolved Depends-on)" in result.stdout
    assert "duplicate Depends-on: dep-target" in result.stdout


def test_depends_on_none_no_note(tmp_path: Path):
    write_item_with_status(tmp_path, "item-z", status_with_depends("none"))
    result = run_checker(tmp_path)
    assert result.returncode == 0
    assert "blocked-by" not in result.stdout
    assert "dangling" not in result.stdout


# --- epic links: unique active/archive target required -----------------------

def test_dangling_epic_reported(tmp_path: Path):
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-missing-epic"))
    result = run_checker(tmp_path)
    assert result.returncode == 1, result.stdout
    assert "dangling Epic: 2026-06-18-missing-epic" in result.stdout


def test_existing_epic_not_reported(tmp_path: Path):
    epics = tmp_path / "work-items" / "epics"
    epics.mkdir(parents=True)
    (epics / "2026-06-18-demo.md").write_text("---\nstatus: active\n---\n", encoding="utf-8")
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-demo"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "dangling Epic" not in result.stdout


def test_archived_epic_is_a_valid_link_target(tmp_path: Path):
    archived = tmp_path / "work-items" / "epics" / "archive" / "2026-06"
    archived.mkdir(parents=True)
    (archived / "2026-06-18-demo.md").write_text("---\nstatus: closed\n---\n", encoding="utf-8")
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-demo"))
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "dangling Epic" not in result.stdout
    assert "duplicate Epic" not in result.stdout


def test_duplicate_active_and_archived_epic_is_rejected(tmp_path: Path):
    epics = tmp_path / "work-items" / "epics"
    archived = epics / "archive" / "2026-06"
    archived.mkdir(parents=True)
    (epics / "2026-06-18-demo.md").write_text("---\nstatus: active\n---\n", encoding="utf-8")
    (archived / "2026-06-18-demo.md").write_text("---\nstatus: closed\n---\n", encoding="utf-8")
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-demo"))
    result = run_checker(tmp_path)
    assert result.returncode == 1, result.stdout
    assert "duplicate Epic: 2026-06-18-demo" in result.stdout
    assert "epics/2026-06-18-demo.md" in result.stdout
    assert "epics/archive/2026-06/2026-06-18-demo.md" in result.stdout


def test_duplicate_epic_across_archive_months_is_rejected(tmp_path: Path):
    epics = tmp_path / "work-items" / "epics" / "archive"
    for month in ("2026-05", "2026-06"):
        archived = epics / month
        archived.mkdir(parents=True)
        (archived / "2026-06-18-demo.md").write_text("---\nstatus: closed\n---\n", encoding="utf-8")
    write_item_with_status(tmp_path, "item-epic", status_with_epic("2026-06-18-demo"))
    result = run_checker(tmp_path)
    assert result.returncode == 1, result.stdout
    assert "duplicate Epic: 2026-06-18-demo" in result.stdout


def test_multiple_active_items_without_epics_surface_adoption_prompt(tmp_path: Path):
    write_valid_item(tmp_path, "item-a")
    write_valid_item(tmp_path, "item-b")
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "no work-items/epics/ directory for multiple active items" in result.stdout


def test_no_epic_rationale_suppresses_adoption_prompt(tmp_path: Path):
    write_item_with_status(tmp_path, "item-a", status_with_no_epic_rationale())
    write_valid_item(tmp_path, "item-b")
    result = run_checker(tmp_path)
    assert result.returncode == 0, result.stdout
    assert "no work-items/epics/ directory" not in result.stdout


def test_checker_reports_stale_running_agent_when_threshold_is_enabled(tmp_path: Path):
    write_valid_item(
        tmp_path,
        "stale-item",
        ledger_event(
            runId="run-stale-001",
            workItem="stale-item",
            status="running",
            gate="none",
            artifact="",
            evidence=[],
            updatedAt="2026-05-03T08:00:00Z",
        ),
    )

    result = run_checker(tmp_path, "--stale-hours", "1", "--now", "2026-05-03T10:30:00Z")

    assert result.returncode == 1
    assert "stale running agent" in result.stdout


def test_checker_stale_check_ages_only_open_v2_launches(
    tmp_path: Path,
):
    item = write_valid_item(tmp_path, "stale-item")
    launch_common = {
        "schemaVersion": 2,
        "workItem": "stale-item",
        "role": "qa-engineer",
        "executionRole": "internal",
        "scope": ["tests/test_work_items_state_checker.py"],
        "artifact": "reviews/qa.md",
        "startedAt": "2026-05-03T08:00:00Z",
        "updatedAt": "2026-05-03T08:00:00Z",
        "lane": "stale-check",
    }
    settled_launch = {
        **launch_common,
        "runId": "launch-settled-001",
        "status": "running",
        "gate": "none",
        "evidence": [],
        "eventKind": "launch",
    }
    terminal = {
        **launch_common,
        "runId": "terminal-settled-001",
        "status": "completed",
        "gate": "PASS",
        "evidence": [{"kind": "command", "ref": "pytest -q"}],
        "eventKind": "terminal",
        "launchRunId": "launch-settled-001",
    }
    unmatched_launch = {
        **launch_common,
        "runId": "launch-unmatched-001",
        "status": "running",
        "gate": "none",
        "evidence": [],
        "eventKind": "launch",
    }
    standalone = {
        **launch_common,
        "runId": "coordinator-standalone-001",
        "role": "lead",
        "executionRole": "main",
        "status": "running",
        "gate": "none",
        "artifact": "",
        "evidence": [],
        "eventKind": "standalone",
    }
    (item / "agent-runs.jsonl").write_text(
        "\n".join(
            json.dumps(event) for event in (settled_launch, terminal, unmatched_launch, standalone)
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_checker(
        tmp_path,
        "--no-strict-revise",
        "--stale-hours",
        "1",
        "--now",
        "2026-05-03T10:30:00Z",
    )

    assert result.returncode == 1, result.stdout
    assert "launch-settled-001: stale running agent" not in result.stdout
    assert "launch-unmatched-001: stale running agent" in result.stdout
    assert "coordinator-standalone-001: stale running agent" not in result.stdout


def test_archive_scan_propagates_security_reviewer_waiver_validity(tmp_path: Path, subtests):
    def archived_case(case_name: str, *, invalid: bool = False, legacy_waiver: bool = False):
        root = tmp_path / case_name
        item_name = f"archived-{case_name}"
        item = root / "work-items" / "archive" / "2026-07" / item_name
        (item / "reviews").mkdir(parents=True)
        (item / "closure.md").write_text(
            "Closed: 2026-07-01\nOutcome: Synthetic archived review fixture.\n",
            encoding="utf-8",
        )
        (item / "reviews" / "security.md").write_text("PASS\n", encoding="utf-8")
        target_id = f"run-archive-{case_name}-target"
        waiver_id = f"run-archive-{case_name}-waiver"
        target = ledger_event(
            schemaVersion=2,
            runId=target_id,
            workItem=item_name,
            role="security-reviewer",
            executionRole="external-reviewer",
            status="revise",
            gate="REVISE",
            artifact="reviews/security.md",
            lane=f"archive-{case_name}",
            findingClass="security",
        )
        waiver = ledger_event(
            schemaVersion=1 if legacy_waiver else 2,
            runId=waiver_id,
            workItem=item_name,
            role="security-reviewer",
            executionRole="internal",
            status="completed",
            gate="WAIVED:security-reviewer",
            scope=[] if invalid else ["archive security review"],
            artifact="reviews/security.md",
            evidence=[{
                "kind": "manual-check",
                "ref": f"security-reviewer waives {target_id}",
            }],
            closesRunIds=[target_id],
        )
        (item / "agent-runs.jsonl").write_text(
            "\n".join(json.dumps(event) for event in (target, waiver)) + "\n",
            encoding="utf-8",
        )
        return run_checker(root), target_id, waiver_id

    with subtests.test(case="legal version-2 waiver"):
        result, target_id, _waiver_id = archived_case("legal")

        assert result.returncode == 0, result.stdout
        assert f"open REVISE obligation survived archival: {target_id}" not in result.stdout
        assert "archive scan clean" in result.stdout

    with subtests.test(case="invalid version-2 waiver"):
        result, target_id, waiver_id = archived_case("invalid", invalid=True)

        assert result.returncode == 1
        assert f"{waiver_id}: scope must be a non-empty list" in result.stdout
        assert f"open REVISE obligation survived archival: {target_id}" in result.stdout

    with subtests.test(case="legacy version-1 waiver"):
        result, target_id, waiver_id = archived_case("legacy", legacy_waiver=True)

        assert result.returncode == 1
        assert f"open REVISE obligation survived archival: {target_id}" in result.stdout
        assert f"{waiver_id}: field closesRunIds requires schemaVersion 2" not in result.stdout


def raw_v2_archived_review_events(item_name: str) -> tuple[dict, dict]:
    target = ledger_event(
        schemaVersion=2,
        runId="run-archive-legacy-target",
        workItem=item_name,
        role="qa-engineer",
        executionRole="internal",
        status="revise",
        gate="REVISE",
        artifact=".scratch/reviews/legacy-qa-pass.md",
        lane="archive-legacy-review",
        effort="high",
        provider="codex",
        findingClass="correctness",
    )
    closer = ledger_event(
        schemaVersion=2,
        runId="run-archive-legacy-closer",
        workItem=item_name,
        role="qa-engineer",
        executionRole="internal",
        status="completed",
        gate="PASS",
        artifact=".scratch/reviews/legacy-qa-pass.md",
        evidence=[{"kind": "review", "ref": "legacy archived review PASS"}],
        lane="archive-legacy-review",
        effort="high",
        provider="codex",
        closesRunIds=[target["runId"]],
    )
    return target, closer


def test_default_archive_scan_uses_logical_owner_not_retained_ledger_basename(tmp_path: Path) -> None:
    checker, owner, roots, goal, write_goal, close_member = _goal_fixture(tmp_path)
    close_member("A", "a")
    close_member("A", "g")
    record = write_goal(terminal=True)
    root = roots["A"]
    archived = owner.resolve_category(root, "work-item:a")
    baseline = run_checker(root)
    assert baseline.returncode == 0, baseline.stdout
    before = owner.observe_readme(root)
    snapshot = archived / "ordinary-attachments" / "retained-copy" / "agent-runs.jsonl"
    snapshot.parent.mkdir(parents=True)
    target, _closer = raw_v2_archived_review_events("retained-copy")
    snapshot.write_text(json.dumps(target) + "\n", encoding="utf-8")
    bytes_before = snapshot.read_bytes()
    result = run_checker(root)
    assert result.returncode == 0 and "retained-copy (ARCHIVED)" not in result.stdout, result.stdout
    assert owner.observe_readme(root) == before and snapshot.read_bytes() == bytes_before
    model = owner.archive_entity_inventory(root / "work-items")
    assert archived in model.logical_work_item_paths and snapshot.parent not in model.logical_work_item_paths
    model.verify()
    ledger = archived / "agent-runs.jsonl"
    target, _closer = raw_v2_archived_review_events(archived.name)
    ledger.write_text(json.dumps(target) + "\n", encoding="utf-8")
    result = run_checker(root)
    assert result.returncode == 1 and f"open REVISE obligation survived archival: {target['runId']}" in result.stdout, result.stdout
    ledger.unlink()
    ledger.mkdir()
    result = run_checker(root)
    assert result.returncode == 1 and "a (ARCHIVED)" in result.stdout, result.stdout
    ledger.rmdir()
    ledger.symlink_to(root / "missing-canonical-ledger")
    result = run_checker(root)
    assert result.returncode == 1, result.stdout
    assert snapshot.read_bytes() == bytes_before


def test_readonly_archive_owner_contract_is_unavailable_or_current_never_empty_fallback(tmp_path: Path) -> None:
    owner = load_checker_module().load_lifecycle_owner()
    root = tmp_path / "repo"
    root.mkdir()
    before = list(root.iterdir())
    absent = owner.archive_entity_inventory(root)
    assert absent.logical_work_item_paths == ()
    absent.verify()
    assert list(root.iterdir()) == before and not (root / ".scratch").exists()
    archive = root / "work-items" / "archive"
    archive.mkdir(parents=True)
    try:
        absent.verify()
    except owner.LifecycleError as error:
        assert error.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("absent archive appearance lost")
    acquired = owner.archive_entity_inventory(root)
    (archive / "2026-10").mkdir()
    try:
        acquired.verify()
    except owner.LifecycleError as error:
        assert error.failure_id == "WI-README-STALE"
    else:
        raise AssertionError("archive membership drift lost")
    assert not (root / ".scratch").exists()


def test_archive_scan_accepts_raw_v2_missing_legacy_review_pointer(tmp_path: Path) -> None:
    item_name = "archived-legacy-review-pointer"
    item = tmp_path / "work-items" / "archive" / "2026-07" / item_name
    item.mkdir(parents=True)
    (item / "closure.md").write_text(
        "Closed: 2026-07-01\nOutcome: Synthetic archived review fixture.\n",
        encoding="utf-8",
    )
    target, closer = raw_v2_archived_review_events(item_name)
    ledger = item / "agent-runs.jsonl"
    ledger.write_text(
        "\n".join(json.dumps(event) for event in (target, closer)) + "\n",
        encoding="utf-8",
    )
    before = ledger.read_bytes()

    result = run_checker(tmp_path, "--telemetry")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "artifact does not exist" not in result.stdout
    assert "open REVISE obligation survived archival" not in result.stdout
    assert "archive-legacy-review-pointer-compat=1" in result.stdout
    assert ledger.read_bytes() == before


def test_archive_review_pointer_closes_only_its_named_revise(tmp_path: Path) -> None:
    validator = load_validator_module()
    item_name = "archived-legacy-review-residual"
    item = tmp_path / "work-items" / "archive" / "2026-07" / item_name
    (item / "reviews").mkdir(parents=True)
    (item / "reviews" / "parked.md").write_text("PARKED\n", encoding="utf-8")
    target, closer = raw_v2_archived_review_events(item_name)
    parked = ledger_event(
        schemaVersion=2,
        runId="run-archive-parked-residual",
        workItem=item_name,
        role="qa-engineer",
        executionRole="internal",
        status="revise",
        gate="REVISE",
        artifact="reviews/parked.md",
        lane="archive-parked-residual",
        effort="high",
        provider="codex",
        findingClass="correctness",
    )
    ledger = item / "agent-runs.jsonl"
    ledger.write_text(
        "\n".join(json.dumps(event) for event in (target, parked, closer)) + "\n",
        encoding="utf-8",
    )
    before = ledger.read_bytes()
    telemetry: dict[str, int] = {}

    errors, open_revise, open_launches = validator.validate_archived_ledger_obligations(
        item, telemetry=telemetry
    )

    assert errors == []
    assert [event["runId"] for event in open_revise] == [parked["runId"]]
    assert open_launches == []
    assert telemetry.get("archive-legacy-review-pointer-compat") == 1
    assert ledger.read_bytes() == before


def test_terminal_archive_preserves_old_lead_review_relation_only_after_close(tmp_path: Path) -> None:
    validator = load_validator_module()
    slug = "archived-lead-review-history"
    artifact = "profession-review.md"
    target = ledger_event(
        schemaVersion=2, runId="run-lead-review-revise", workItem=slug,
        role="lead", executionRole="main", status="revise", gate="REVISE",
        artifact=artifact, lane="profession-review", effort="medium", provider="codex",
        startedAt="2026-09-09T10:00:00Z", updatedAt="2026-09-09T10:00:00Z",
    )
    closer = ledger_event(
        schemaVersion=2, runId="run-qa-reverified-lead", workItem=slug,
        role="qa-engineer", executionRole="internal", assignedRole="lead",
        status="completed", gate="PASS", artifact=artifact,
        lane="profession-review", effort="medium", provider="codex",
        closesRunIds=[target["runId"]],
        evidence=[{"kind": "review", "ref": artifact}],
        startedAt="2026-09-09T10:05:00Z", updatedAt="2026-09-09T10:05:00Z",
    )
    raw_ledger = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in (target, closer)).encode("utf-8")

    current = tmp_path / "current" / "work-items" / "active" / slug
    preclose = tmp_path / "preclose" / "work-items" / "archive" / "2026-09" / slug
    terminal = tmp_path / "terminal" / "work-items" / "archive" / "2026-09" / slug
    for item in (current, preclose, terminal):
        item.mkdir(parents=True)
        (item / artifact).write_text("reviewed evidence\n", encoding="utf-8")
        (item / "agent-runs.jsonl").write_bytes(raw_ledger)
    (current / "status.md").write_text(valid_status(), encoding="utf-8")
    (terminal / "closure.md").write_text(
        "Outcome: completed.\nClosed: 2026-09-10T13:48:21Z\n"
        "Evidence: profession-review.md.\nResidual risk: none.\n", encoding="utf-8",
    )

    try:
        validator.validate_closure(
            [target, closer], [], event_validity=[True, True],
            _archived_preclose_v2_rows=frozenset({1, 2}),
        )
    except TypeError:
        pass
    else:
        raise AssertionError("public validate_closure accepted caller-selected archive authority")

    current_errors = validator.validate_work_item(current)
    assert any("C3-reviewed-role-fail" in error for error in current_errors), current_errors
    assert any("open REVISE obligation" in error for error in current_errors), current_errors
    preclose_errors, preclose_open, _ = validator.validate_archived_ledger_obligations(preclose)
    assert preclose_errors or preclose_open
    assert any("WI-LEDGER-ARCHIVE-CLOSURE-EVIDENCE: missing" in error for error in preclose_errors), preclose_errors
    terminal_errors, terminal_open, terminal_launches = validator.validate_archived_ledger_obligations(terminal)
    assert terminal_errors == [] and terminal_open == [] and terminal_launches == []
    assert all((item / "agent-runs.jsonl").read_bytes() == raw_ledger for item in (current, preclose, terminal))

    direct_errors: list[str] = []
    validator.validate_closure([target, closer], direct_errors, event_validity=[True, True])
    assert any("C3-reviewed-role-fail" in error for error in direct_errors), direct_errors

    late = tmp_path / "late" / "work-items" / "archive" / "2026-09" / slug
    shutil.copytree(terminal, late)
    late_closer = {**closer, "updatedAt": "2026-09-11T10:05:00Z"}
    (late / "agent-runs.jsonl").write_text(
        "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in (target, late_closer)),
        encoding="utf-8",
    )
    late_errors, late_open, _ = validator.validate_archived_ledger_obligations(late)
    assert any("C3-reviewed-role-fail" in error for error in late_errors), late_errors
    assert late_open

    invalid_close = tmp_path / "invalid" / "work-items" / "archive" / "2026-09" / slug
    shutil.copytree(terminal, invalid_close)
    (invalid_close / "closure.md").write_text("Closed: 2026-13-10T13:48:21Z\n", encoding="utf-8")
    invalid_errors, invalid_open, _ = validator.validate_archived_ledger_obligations(invalid_close)
    assert any("WI-LEDGER-ARCHIVE-CLOSURE-EVIDENCE: invalid" in error for error in invalid_errors), invalid_errors
    assert any("C3-reviewed-role-fail" in error for error in invalid_errors), invalid_errors
    assert invalid_open

    wrong_month = tmp_path / "wrong-month" / "work-items" / "archive" / "2026-08" / slug
    shutil.copytree(terminal, wrong_month)
    month_errors, month_open, _ = validator.validate_archived_ledger_obligations(wrong_month)
    assert any("WI-LEDGER-ARCHIVE-CLOSURE-EVIDENCE: month" in error for error in month_errors), month_errors
    assert month_open


def test_archive_review_pointer_compatibility_is_strictly_bounded(tmp_path: Path) -> None:
    validator = load_validator_module()
    item = tmp_path / "work-items" / "archive" / "2026-07" / "bounded-review-pointer"
    item.mkdir(parents=True)
    base = ledger_event(
        schemaVersion=2,
        runId="run-bounded-review-pointer",
        workItem=item.name,
        role="qa-engineer",
        executionRole="internal",
        status="completed",
        gate="PASS",
        artifact=".scratch/reviews/missing.md",
        evidence=[{"kind": "review", "ref": "legacy archived review PASS"}],
    )

    def derive(event: dict, transformation: str = "raw", authorizations=None):
        encoded = json.dumps(
            event, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        event_sha = hashlib.sha256(encoded).hexdigest()
        row = validator.LedgerProjectionRowV1(
            event, 1, event_sha, event_sha, transformation
        )
        errors: list[str] = []
        validity, closure_validity = validator.derive_archived_event_validity(
            [event], item, errors, authorizations or {}, rows=(row,)
        )
        return errors, validity, closure_validity

    for name, update in (
        ("repository path", {"artifact": "reviews/missing.md"}),
        ("scratch outside reviews", {"artifact": ".scratch/output/missing.md"}),
        ("reviews directory itself", {"artifact": ".scratch/reviews"}),
        ("typed scratch identity", {"scratchEvidence": []}),
    ):
        errors, validity, closure_validity = derive({**base, **update})
        assert any("artifact does not exist" in error for error in errors), name
        assert validity == [False], name
        assert closure_validity == [False], name

    for transformation in ("manifest-projected", "migration-replaced"):
        errors, validity, closure_validity = derive(base, transformation)
        assert any("artifact does not exist" in error for error in errors), transformation
        assert validity == [False], transformation
        assert closure_validity == [False], transformation

    active = tmp_path / "work-items" / "active" / "bounded-review-pointer"
    active.mkdir(parents=True)
    active_errors: list[str] = []
    assert not validator.validate_event(base, active, set(), active_errors)
    assert any("artifact does not exist" in error for error in active_errors)

    present = item / ".scratch" / "reviews" / "present.md"
    present.parent.mkdir(parents=True)
    present.write_text("present but typed identity is malformed\n", encoding="utf-8")
    existing_mismatch = {
        **base,
        "artifact": ".scratch/reviews/present.md",
        "scratchEvidence": [],
    }
    errors, validity, closure_validity = derive(existing_mismatch)
    assert any("scratchEvidence" in error for error in errors)
    assert validity == [False]
    assert closure_validity == [False]

    authorized = {**base, "artifactRevision": "a" * 64}
    encoded = json.dumps(
        authorized, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    event_sha = hashlib.sha256(encoded).hexdigest()
    authorization = validator.HistoricalArtifactAuthorization(
        1,
        event_sha,
        event_sha,
        authorized["runId"],
        authorized["artifact"],
        authorized["artifactRevision"],
    )
    errors, validity, closure_validity = derive(authorized, authorizations={1: authorization})
    assert errors == []
    assert validity == [True]
    assert closure_validity == [False]

    drifted_authorization = validator.HistoricalArtifactAuthorization(
        1,
        "0" * 64,
        event_sha,
        authorized["runId"],
        authorized["artifact"],
        authorized["artifactRevision"],
    )
    errors, validity, closure_validity = derive(
        authorized, authorizations={1: drifted_authorization}
    )
    assert any("artifact does not exist" in error for error in errors)
    assert validity == [False]
    assert closure_validity == [False]

    version_three = {"schemaVersion": 3}
    errors, validity, closure_validity = derive(version_three)
    assert errors == []
    assert validity == [False]
    assert closure_validity == [False]


def test_active_only_keeps_periodic_archive_failures_out_of_publication_scope(
    tmp_path: Path,
) -> None:
    (tmp_path / "work-items" / "active").mkdir(parents=True)
    item_name = "archived-open-revise"
    item = tmp_path / "work-items" / "archive" / "2026-07" / item_name
    (item / "reviews").mkdir(parents=True)
    (item / "closure.md").write_text(
        "Closed: 2026-07-01\nOutcome: Synthetic archived review fixture.\n",
        encoding="utf-8",
    )
    (item / "reviews" / "qa.md").write_text("REVISE\n", encoding="utf-8")
    revise = ledger_event(
        schemaVersion=2,
        runId="run-archived-open-revise-001",
        workItem=item_name,
        role="qa-engineer",
        executionRole="internal",
        status="revise",
        gate="REVISE",
        artifact="reviews/qa.md",
        lane="archived-review",
        findingClass="correctness",
    )
    (item / "agent-runs.jsonl").write_text(
        json.dumps(revise) + "\n", encoding="utf-8"
    )

    periodic = run_checker(tmp_path)
    publication = run_checker(tmp_path, "--active-only")

    assert periodic.returncode == 1
    assert "open REVISE obligation survived archival" in periodic.stdout
    assert publication.returncode == 0, publication.stdout
    assert "(ARCHIVED)" not in publication.stdout
    assert "archive obligation scan skipped" in publication.stdout


def test_publication_preflight_ignores_unrelated_active_lifecycle_state(
    tmp_path: Path, monkeypatch
) -> None:
    """Removing the lifecycle predicate must not bypass the scanner or Git target check."""
    gate_path = ROOT / "scripts" / "check-publication-gate.py"
    spec = importlib.util.spec_from_file_location("publication_gate", gate_path)
    assert spec is not None and spec.loader is not None
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    calls: list[list[str]] = []

    def fake_run(args, **_kwargs):
        calls.append(args)
        if args[0] == sys.executable:
            return subprocess.CompletedProcess(args, 0)
        raise AssertionError(f"unexpected subprocess call: {args}")

    monkeypatch.setattr(gate, "_git_root", lambda: tmp_path)
    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    monkeypatch.setattr(
        gate,
        "_run",
        lambda args, **_kwargs: subprocess.CompletedProcess(args, 0, stdout=b""),
    )
    (tmp_path / "work-items" / "active" / "unrelated").mkdir(parents=True)

    assert gate.main([]) == 0
    assert calls == [[sys.executable, str(tmp_path / "src.codex" / "skills" / "lead" / "scripts" / "check-publication-safety.py")]]


def test_publication_preflight_keeps_release_note_requirement_with_active_work(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """Lifecycle separation must not turn a release-relevant staged target into PASS."""
    gate_path = ROOT / "scripts" / "check-publication-gate.py"
    spec = importlib.util.spec_from_file_location("publication_gate_release", gate_path)
    assert spec is not None and spec.loader is not None
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    monkeypatch.setattr(gate, "_git_root", lambda: tmp_path)
    monkeypatch.setattr(
        gate.subprocess,
        "run",
        lambda args, **_kwargs: subprocess.CompletedProcess(args, 0),
    )
    monkeypatch.setattr(
        gate,
        "_run",
        lambda args, **_kwargs: subprocess.CompletedProcess(
            args, 0, stdout=b"scripts/changed.py\\0"
        ),
    )
    (tmp_path / "work-items" / "active" / "unrelated").mkdir(parents=True)

    assert gate.main([]) == 1
    assert "release-relevant staged changes require" in capsys.readouterr().err


def test_archive_scan_keeps_skipped_legacy_positions_for_v2_closure_targets(tmp_path: Path):
    item = tmp_path / "work-items" / "archive" / "2026-07" / "archived-legacy-target"
    (item / "reviews").mkdir(parents=True)
    (item / "reviews" / "security.md").write_text("PASS\n", encoding="utf-8")
    target_id = "run-archive-legacy-target"
    target = ledger_event(
        schemaVersion=1,
        runId=target_id,
        workItem="archived-legacy-target",
        role="security-reviewer",
        executionRole="external-reviewer",
        status="revise",
        gate="REVISE",
        artifact="reviews/security.md",
        lane="archive-legacy-target",
        findingClass="security",
    )
    closer = ledger_event(
        schemaVersion=2,
        runId="run-archive-v2-closer",
        workItem="archived-legacy-target",
        role="security-reviewer",
        executionRole="internal",
        status="completed",
        gate="WAIVED:security-reviewer",
        scope=["archive security review"],
        artifact="reviews/security.md",
        evidence=[{"kind": "manual-check", "ref": f"security-reviewer waives {target_id}"}],
        closesRunIds=[target_id],
    )
    (item / "agent-runs.jsonl").write_text(
        "\n".join(json.dumps(event) for event in (target, closer)) + "\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "does not reference an earlier event (C1)" not in result.stdout


def _numeric_v1_archive_case(root: Path, *events: dict) -> Path:
    item = root / "work-items" / "archive" / "2026-07" / "numeric-v1-closure"
    (item / "reviews").mkdir(parents=True)
    (item / "reviews" / "security.md").write_text("REVISE then PASS\n", encoding="utf-8")
    (item / "reviews" / "other.md").write_text("different angle\n", encoding="utf-8")
    (item / "agent-runs.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8",
    )
    return item


def _numeric_v1_revise(**updates: object) -> dict:
    return ledger_event(
        schemaVersion=1, runId="run-numeric-v1-revise", workItem="numeric-v1-closure",
        role="security-reviewer", executionRole="external-reviewer",
        status="completed", gate="REVISE", artifact="reviews/security.md",
        **updates,
    )


def _numeric_v2_pass(**updates: object) -> dict:
    return ledger_event(
        schemaVersion=2, runId="run-numeric-v2-pass", workItem="numeric-v1-closure",
        role="security-reviewer", executionRole="internal",
        status="completed", gate="PASS", artifact="reviews/security.md",
        lane="security-review",
        closesRunIds=["run-numeric-v1-revise"],
        evidence=[{"kind": "review", "ref": "independent recheck"}],
        **updates,
    )


def test_archived_numeric_v1_revise_is_only_a_linked_v2_target(tmp_path: Path) -> None:
    validator = load_validator_module()
    authority = []
    linked = _numeric_v1_archive_case(
        tmp_path / "linked", _numeric_v1_revise(), _numeric_v2_pass(),
    )
    before = (linked / "agent-runs.jsonl").read_bytes()

    errors, open_revise, open_launches = validator.validate_archived_ledger_obligations(
        linked, authority_state_out=authority
    )

    assert errors == []
    assert open_revise == [] and open_launches == []
    assert (linked / "agent-runs.jsonl").read_bytes() == before
    assert len(authority) == 1
    linked_mask = authority[0][1]
    assert (
        linked_mask.launch_eligible,
        linked_mask.terminal_eligible,
        linked_mask.revise_target_eligible,
        linked_mask.closer_eligible,
        linked_mask.artifact_evidence_eligible,
    ) == (False, False, True, False, False)

    unlinked = _numeric_v1_archive_case(tmp_path / "unlinked", _numeric_v1_revise())
    unlinked_before = (unlinked / "agent-runs.jsonl").read_bytes()
    assert validator.validate_archived_ledger_obligations(
        unlinked, authority_state_out=authority
    ) == ([], [], [])
    assert len(authority) == 2
    assert not any(vars(authority[1][1]).values())
    assert (unlinked / "agent-runs.jsonl").read_bytes() == unlinked_before
    active_errors: list[str] = []
    validator.validate_closure(
        [_numeric_v1_revise(), _numeric_v2_pass()], active_errors,
        event_validity=[False, True],
    )
    assert any("(C2)" in error for error in active_errors)


def test_archived_numeric_v1_revise_rejects_invalid_targets_and_order(tmp_path: Path) -> None:
    validator = load_validator_module()
    target = _numeric_v1_revise()
    closer = _numeric_v2_pass()
    cases = (
        ("later", (closer, target), "(C1)"),
        ("non-revise", ({**target, "gate": "none"}, closer), "(C2)"),
        ("wrong-item", ({**target, "workItem": "different-item"}, closer), "(C2)"),
        ("wrong-epoch", ({**target, "schemaVersion": True}, closer), "(C2)"),
        ("invalid-shape", ({**target, "status": "not-a-status"}, closer), "(C2)"),
        ("duplicate-id", (target, {**target}, closer), "(C2)"),
        ("casefold-duplicate", (target, {**target, "runId": target["runId"].upper()}, closer), "(C2)"),
        ("case-mismatch-link", (target, {**closer, "closesRunIds": [target["runId"].upper()]}), "(C1)"),
    )
    for name, events, expected in cases:
        item = _numeric_v1_archive_case(tmp_path / name, *events)
        errors, _open_revise, _open_launches = validator.validate_archived_ledger_obligations(item)
        assert any(expected in error for error in errors), (name, errors)


def test_archived_numeric_v1_revise_projected_row_is_not_a_raw_target(
    tmp_path: Path, monkeypatch,
) -> None:
    validator = load_validator_module()
    item = _numeric_v1_archive_case(
        tmp_path, _numeric_v1_revise(), _numeric_v2_pass(),
    )
    original = validator._project_manifest_rows

    def projected(rows, work_item, ledger, ledger_bytes):
        effective, counters, errors = original(rows, work_item, ledger, ledger_bytes)
        return (
            tuple(
                replace(row, transformation="manifest-profile")
                if row.event.get("schemaVersion") == 1 else row
                for row in effective
            ),
            counters,
            errors,
        )

    monkeypatch.setattr(validator, "_project_manifest_rows", projected)
    errors, _open_revise, _open_launches = validator.validate_archived_ledger_obligations(item)
    assert any("(C2)" in error for error in errors), errors


def test_archived_numeric_v1_revise_exposes_later_closure_gates(tmp_path: Path) -> None:
    validator = load_validator_module()
    target = _numeric_v1_revise()
    wrong_artifact = ledger_event(
        schemaVersion=2, runId="run-wrong-artifact", workItem="numeric-v1-closure",
        role="security-reviewer", executionRole="internal", status="completed", gate="PASS",
        artifact="reviews/other.md", lane="security-review", closesRunIds=[target["runId"]],
        evidence=[{"kind": "review", "ref": "independent recheck"}],
    )
    user_waiver = ledger_event(
        schemaVersion=2, runId="run-user-waiver", workItem="numeric-v1-closure",
        role="lead", executionRole="main", status="completed", gate="WAIVED:user",
        closesRunIds=[target["runId"]],
        evidence=[{"kind": "manual-check", "ref": "operator waives run-numeric-v1-revise"}],
    )
    for name, closer, expected in (
        ("c3", wrong_artifact, "(C3)"), ("c5", user_waiver, "(C5)"),
    ):
        item = _numeric_v1_archive_case(tmp_path / name, target, closer)
        errors, _open_revise, _open_launches = validator.validate_archived_ledger_obligations(item)
        assert any(expected in error for error in errors), (name, errors)
        assert not any("(C2)" in error for error in errors), (name, errors)


def test_archived_numeric_v1_revise_rejects_invalid_duplicate_closer(tmp_path: Path) -> None:
    validator = load_validator_module()
    target = _numeric_v1_revise()
    closer = _numeric_v2_pass()
    invalid = _numeric_v1_archive_case(
        tmp_path / "invalid", target, {**closer, "status": "cancelled"},
    )
    errors, _open_revise, _open_launches = validator.validate_archived_ledger_obligations(invalid)
    assert errors
    assert not any("(C2)" in error for error in errors), errors

    duplicate = _numeric_v1_archive_case(
        tmp_path / "duplicate", target, closer,
        {**closer, "runId": "run-second-waiver"},
    )
    errors, _open_revise, _open_launches = validator.validate_archived_ledger_obligations(duplicate)
    assert any("(C2 unique discharge)" in error for error in errors), errors


def test_done_predicate_twin_not_drifted():
    # The state-checker re-implements the SEN-0 archival-orphan invariant's
    # DONE_STATE regex (no shared import across the sentinel/validator
    # boundary — workitem_sentinels.py must never be imported BY the
    # validator's twin logic, only the reverse; design.md §3.2). Guard against
    # silent drift: the distinctive pattern line must appear verbatim in BOTH
    # files. As of the sentinel-registry migration
    # (2026-07-25-review-round-cap-enforcement), the regex's owning file is
    # `workitem_sentinels.py`, not `check-work-items-archival-stop.py` (now a
    # thin adapter that imports it) — the twin-check follows the regex to its
    # new home rather than the file that used to hold it.
    line = r'r"\s*\*{0,3}\s*:\s*\*{0,3}\s*(?:closed|done|complete|completed|archived)(?![\w-])"'
    sentinels = (ROOT / "src.claude" / "agents" / "scripts" / "workitem_sentinels.py").read_text(encoding="utf-8")
    checker = CHECKER.read_text(encoding="utf-8")
    assert line in sentinels, "workitem_sentinels.py DONE_STATE pattern changed — update the twin in check-work-items-state.py"
    assert line in checker, "check-work-items-state.py DONE_STATE pattern drifted from workitem_sentinels.py"


class TestArchiveOnlyDependencyTerminality(unittest.TestCase):
    def test_active_semantic_done_is_not_terminal_until_archive_move(self) -> None:
        lifecycle = load_checker_module().load_lifecycle_owner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "work-items" / "active"
            archive = root / "work-items" / "archive"
            item = active / "dependency"
            item.mkdir(parents=True)
            (item / "status.md").write_text("status: completed\n", encoding="utf-8")
            (item / "closure.md").write_text(
                "Closed: 2026-07-31T00:00:00Z\n",
                encoding="utf-8",
            )
            self.assertEqual(
                lifecycle.work_item_dependency_state(root, "dependency"),
                "open",
            )
            archived = archive / "2026-07" / "dependency"
            archived.parent.mkdir(parents=True)
            item.replace(archived)
            self.assertEqual(
                lifecycle.work_item_dependency_state(root, "dependency"),
                "done",
            )


def test_decision_schema_failure_reaches_repository_state_checker(tmp_path: Path) -> None:
    decision = (
        tmp_path
        / "work-items"
        / "decisions"
        / "2026-08-11-schema-test.md"
    )
    decision.parent.mkdir(parents=True)
    decision.write_text(
        "---\nstatus: proposed\nnot-a-field\ndate: 2026-08-11\n---\n"
        "\n# Decision: malformed\n",
        encoding="utf-8",
    )
    entry = {
        "path": decision.name,
        "sha256": hashlib.sha256(decision.read_bytes()).hexdigest().upper(),
        "state": "admitted",
    }
    baseline = hashlib.sha256(
        f"{entry['path']}\0{entry['sha256']}\n".encode("utf-8")
    ).hexdigest().upper()
    policy_slug = "2026-08-18-current-decision-schema-versioned-read-compatibility"
    (decision.parent / f"{policy_slug}.md").write_text(
        "\n".join(
            [
                f"- id: {policy_slug}",
                "- status: accepted",
                "- date: 2026-08-18",
                "- decided-by: $architect",
                "- context: schema-test",
                "- supersedes: none",
                "- superseded-by: none",
                "- accepted-evidence: fixture",
                "- v0-manifest: work-items/decision-v0-compatibility.json",
                f"- v0-baseline-sha256: {baseline}",
                "- v0-cutover-date: 2026-08-18",
                "",
                f"# Decision: {policy_slug}",
                "",
                "## Decision",
                "Fixture policy anchor.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "work-items" / "decision-v0-compatibility.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "policyDecision": policy_slug,
                "cutoverDate": "2026-08-18",
                "baselineSha256": baseline,
                "entries": [entry],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "WI-DECISION-V0-SCHEMA-INVALID" in result.stdout


def test_checker_configured_component_preserves_base_dependency_scope(tmp_path: Path) -> None:
    base = tmp_path / "base"
    component = base / "component"
    write_valid_item(base, "dual-dep")
    backlog = base / "work-items" / "backlog"
    backlog.mkdir(parents=True)
    (backlog / "dual-dep.md").write_text("status: candidate\n", encoding="utf-8")
    write_valid_item(component, "dual-dep")
    write_valid_item(component, "missing-dep")
    write_item_with_status(component, "selected-item", status_with_depends("dual-dep, missing-dep"))
    result = run_checker(base, "--active-dir", "component/work-items/active")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "WI-CATEGORY-DUAL-LOCATION" in result.stdout
    assert "duplicate Depends-on: dual-dep" in result.stdout
    assert "dangling Depends-on: missing-dep" in result.stdout
    assert "PASS selected-item" in result.stdout


def test_checker_aliases_validate_base_transfer_receipt(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("checker_base_transfer_fixture", ROOT / "tests" / "test_legacy_obligation_migration.py")
    support = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(support)
    base = tmp_path / "base"
    fixture = support.transfer_fixture(base)
    receipt = support.run_transfer(fixture)
    receipt_path = base / receipt["archivePath"] / "lifecycle-transition-receipt.json"
    original = receipt_path.read_bytes()
    archive = receipt_path.parent
    authority = []
    errors, open_revise, open_launches = load_validator_module().validate_archived_ledger_obligations(
        archive, authority_state_out=authority
    )
    expected_revise = [row["runId"] for row in receipt["obligations"]]
    assert errors == []
    assert [row["runId"] for row in open_revise] == expected_revise
    assert open_launches == []
    assert (archive / "agent-runs.jsonl").read_bytes() == fixture["ledgerBefore"]
    raw_events = [json.loads(line) for line in fixture["ledgerBefore"].splitlines()]
    terminal_ids = [raw_events[ordinal - 1]["runId"] for ordinal, mask in authority[0].items()
                    if mask.terminal_eligible]
    target = next(event for event in raw_events if event["runId"] == expected_revise[0])
    assert terminal_ids == [f"{target['launchRunId']}-migration-neutral"]
    for alias, active in ((base, "work-items/active"), (base / "work-items", "active")):
        full = run_checker(alias, "--active-dir", active)
        assert full.returncode == 1, full.stdout + full.stderr
        assert f"open REVISE obligation survived archival: {expected_revise[0]}" in full.stdout
        assert "duplicate terminal" not in full.stdout
        assert "FAIL obligation transfer ownership" not in full.stdout
        checked = run_checker(alias, "--active-dir", active, "--active-only")
        assert checked.returncode == 0, checked.stdout + checked.stderr
    changed = dict(receipt)
    changed["workItem"] = "wrong-base-owner"
    receipt_path.write_text(json.dumps(changed, sort_keys=True) + "\n", encoding="utf-8")
    try:
        for alias, active in ((base, "work-items/active"), (base / "work-items", "active")):
            checked = run_checker(alias, "--active-dir", active, "--active-only")
            assert checked.returncode == 1, checked.stdout + checked.stderr
            assert "FAIL obligation transfer ownership" in checked.stdout
    finally:
        receipt_path.write_bytes(original)
