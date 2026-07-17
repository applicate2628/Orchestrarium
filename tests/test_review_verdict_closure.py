"""REVISE-closure discipline (decision 2026-07-16-review-verdict-closure, minimal slice).

Falsifiers accumulated across the 12-round design loop. The centerpiece is the REPLAY test:
this session's real precedent (reviewer returned REVISE; author fixed findings; mechanical
validator went green; author closed the gate himself) must FAIL mechanically until a valid
re-verification closer is appended.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "validate_work_item_state", ROOT / "scripts" / "validate-work-item-state.py"
)
vws = importlib.util.module_from_spec(_SPEC)
sys.modules["validate_work_item_state"] = vws
_SPEC.loader.exec_module(vws)

STATUS_MD = """# Status

## Current state
open

## Active agents
- none

## Completed agents
- none

## Next action
n/a
"""


def _event(run_id: str, **over) -> dict:
    base = {
        "schemaVersion": 2,
        "runId": run_id,
        "workItem": "fixture-item",
        "role": "architecture-reviewer",
        "executionRole": "external-reviewer",
        "status": "completed",
        "gate": "none",
        "scope": ["fixture"],
        "startedAt": "2026-07-16T10:00:00Z",
        "updatedAt": "2026-07-16T10:00:00Z",
    }
    base.update(over)
    return base


class ClosureFixture(unittest.TestCase):
    def _write(self, events: list[dict]) -> Path:
        import json

        td = Path(tempfile.mkdtemp())
        (td / "status.md").write_text(STATUS_MD, encoding="utf-8")
        # PASS-gate events require their artifact to exist inside the work item.
        (td / "design.md").write_text("fixture artifact\n", encoding="utf-8")
        (td / "a.md").write_text("fixture artifact\n", encoding="utf-8")
        with (td / "agent-runs.jsonl").open("w", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")
        return td

    def _validate(self, events: list[dict], strict: bool = True) -> list[str]:
        item = self._write(events)
        return vws.validate_work_item(item, strict_revise=strict)

    # ---------- THE REPLAY (acceptance case 3) ----------

    def test_replay_precedent_fails_until_valid_closer(self) -> None:
        revise = _event(
            "run-00000001-revise",
            gate="REVISE",
            status="revise",
            artifact="design.md",
            lane="architecture-deep",
            effort="xhigh",
            provider="codex",
            findingClass="correctness",
        )
        # Author fixed the findings; the mechanical validator is green; a validator-run
        # PASS event WITHOUT a closure relation must NOT discharge the obligation.
        validator_green = _event(
            "run-00000002-qagreen",
            gate="PASS",
            role="qa-engineer",
            executionRole="internal",
            artifact="agent-runs.jsonl",
            evidence=[{"kind": "command", "ref": "validate-skill-pack.sh = PASS"}],
        )
        errors = self._validate([revise, validator_green])
        self.assertTrue(any("open REVISE obligation" in e for e in errors), errors)

        # A QA PASS naming the runId still fails: even with matching artifact/lane it has
        # no authority over the architecture angle (C3). (With a mismatched artifact it
        # fails even earlier on the artifact rule — also verified, defense in depth.)
        qa_close = dict(
            validator_green,
            runId="run-00000003-qaclose",
            closesRunIds=["run-00000001-revise"],
            artifact="design.md",
            lane="architecture-deep",
        )
        errors = self._validate([revise, qa_close])
        self.assertTrue(any("(C3)" in e and "authority" in e for e in errors), errors)
        qa_wrong_artifact = dict(qa_close, runId="run-00000003b-wrongart", artifact="agent-runs.jsonl")
        errors = self._validate([revise, qa_wrong_artifact])
        self.assertTrue(any("artifact" in e and "(C3)" in e for e in errors), errors)

        # The SAME angle re-verifying with an explicit closure relation discharges it.
        real_close = _event(
            "run-00000004-reclose",
            gate="PASS",
            artifact="design.md",
            lane="architecture-deep",
            effort="xhigh",
            provider="codex",
            closesRunIds=["run-00000001-revise"],
            evidence=[{"kind": "review", "ref": ".scratch/codex-prompts/re-review.out"}],
        )
        errors = self._validate([revise, real_close])
        self.assertEqual(errors, [], errors)

    # ---------- closure relation rules ----------

    def test_c1_forward_reference_fails(self) -> None:
        closer = _event(
            "run-00000010-closer",
            gate="PASS",
            artifact="design.md",
            closesRunIds=["run-00000011-later"],
            evidence=[{"kind": "review", "ref": "x"}],
        )
        revise = _event("run-00000011-later", gate="REVISE", status="revise", artifact="design.md")
        errors = self._validate([closer, revise])
        self.assertTrue(any("(C1)" in e for e in errors), errors)

    def test_c2_non_revise_target_fails(self) -> None:
        plain = _event("run-00000020-plain", gate="advisory")
        closer = _event(
            "run-00000021-closer",
            gate="PASS",
            artifact="design.md",
            closesRunIds=["run-00000020-plain"],
            evidence=[{"kind": "review", "ref": "x"}],
        )
        errors = self._validate([plain, closer])
        self.assertTrue(any("(C2)" in e for e in errors), errors)

    def test_c2_double_discharge_fails(self) -> None:
        revise = _event("run-00000030-revise", gate="REVISE", status="revise", artifact="a.md")
        c1 = _event(
            "run-00000031-c1", gate="PASS", artifact="a.md",
            closesRunIds=["run-00000030-revise"], evidence=[{"kind": "review", "ref": "x"}],
        )
        c2 = _event(
            "run-00000032-c2", gate="PASS", artifact="a.md",
            closesRunIds=["run-00000030-revise"], evidence=[{"kind": "review", "ref": "x"}],
        )
        errors = self._validate([revise, c1, c2])
        self.assertTrue(any("already discharged" in e for e in errors), errors)

    def test_c3_artifact_and_lane_mismatch_fail(self) -> None:
        revise = _event(
            "run-00000040-revise", gate="REVISE", status="revise",
            artifact="a.md", lane="architecture-deep",
        )
        wrong_artifact = _event(
            "run-00000041-wart", gate="PASS", artifact="b.md", lane="architecture-deep",
            closesRunIds=["run-00000040-revise"], evidence=[{"kind": "review", "ref": "x"}],
        )
        errors = self._validate([revise, wrong_artifact])
        self.assertTrue(any("artifact" in e and "(C3)" in e for e in errors), errors)

        wrong_lane = _event(
            "run-00000042-wlane", gate="PASS", artifact="a.md", lane="security-adversarial",
            closesRunIds=["run-00000040-revise"], evidence=[{"kind": "review", "ref": "x"}],
        )
        errors = self._validate([revise, wrong_lane])
        self.assertTrue(any("lane" in e and "(C3)" in e for e in errors), errors)

    def test_c3_same_provider_lower_effort_fails(self) -> None:
        revise = _event(
            "run-00000050-revise", gate="REVISE", status="revise",
            artifact="a.md", effort="xhigh", provider="codex",
        )
        weak = _event(
            "run-00000051-weak", gate="PASS", artifact="a.md", effort="high", provider="codex",
            closesRunIds=["run-00000050-revise"], evidence=[{"kind": "review", "ref": "x"}],
        )
        errors = self._validate([revise, weak])
        self.assertTrue(any("effort" in e and "(C3" in e for e in errors), errors)

    # ---------- typed waiver ----------

    def test_waiver_shape_and_protected_boundary(self) -> None:
        revise = _event(
            "run-00000060-revise", gate="REVISE", status="revise",
            artifact="a.md", findingClass="publication-safety",
        )
        waiver = _event(
            "run-00000061-waiver", gate="WAIVED:user", status="completed",
            closesRunIds=["run-00000060-revise"],
            evidence=[{"kind": "manual-check", "ref": "operator said: ship run-00000060-revise and run-00000062-rev2 with known issue"}],
        )
        errors = self._validate([revise, waiver])
        self.assertTrue(any("(C5)" in e for e in errors), errors)  # protected class -> non-waivable

        ordinary = dict(revise, runId="run-00000062-rev2", findingClass="correctness")
        waiver2 = dict(waiver, runId="run-00000063-waiv2", closesRunIds=["run-00000062-rev2"])
        errors = self._validate([ordinary, waiver2])
        self.assertEqual(errors, [], errors)  # legitimate operator waiver needs no reviewer role

        bad_status = dict(waiver2, runId="run-00000064-bad", status="cancelled")
        errors = self._validate([ordinary, bad_status])
        self.assertTrue(any("WAIVED:user requires completed status" in e for e in errors), errors)

        no_evidence = dict(waiver2, runId="run-00000065-noev")
        no_evidence.pop("evidence")
        errors = self._validate([ordinary, no_evidence])
        self.assertTrue(any("manual-check" in e for e in errors), errors)

    # ---------- lifecycle ----------

    def test_lifecycle_terminal_rules(self) -> None:
        launch = _event("run-00000070-launch", eventKind="launch", status="running")
        term = _event(
            "run-00000071-term", eventKind="terminal", launchRunId="run-00000070-launch",
            status="blocked", gate="none",
        )
        errors = self._validate([launch, term], strict=False)
        self.assertEqual(errors, [], errors)

        dangling = dict(term, runId="run-00000072-dang", launchRunId="run-00000099-nope")
        errors = self._validate([launch, dangling], strict=False)
        self.assertTrue(any("does not reference an earlier event" in e for e in errors), errors)

        dup = dict(term, runId="run-00000073-dup")
        errors = self._validate([launch, term, dup], strict=False)
        self.assertTrue(any("duplicate terminal" in e for e in errors), errors)

        no_launch_field = _event("run-00000074-nolaunch", eventKind="terminal", status="blocked")
        errors = self._validate([no_launch_field], strict=False)
        self.assertTrue(any("requires launchRunId" in e for e in errors), errors)

    # ---------- Terra impl-review falsifiers (round: implementation diff) ----------

    def test_author_side_closer_fails(self) -> None:
        # The founding failure mode itself: the AUTHOR (executionRole main) closing
        # a reviewer's REVISE. C3 requires a reviewer-side closer.
        revise = _event("run-00000100-revise", gate="REVISE", status="revise", artifact="a.md")
        author_close = _event(
            "run-00000101-author", gate="PASS", artifact="a.md",
            executionRole="main",
            closesRunIds=["run-00000100-revise"], evidence=[{"kind": "review", "ref": "x"}],
        )
        errors = self._validate([revise, author_close])
        self.assertTrue(any("reviewer-side" in e and "(C3)" in e for e in errors), errors)

    def test_effort_omission_is_not_a_bypass(self) -> None:
        revise = _event(
            "run-00000110-revise", gate="REVISE", status="revise",
            artifact="a.md", effort="xhigh", provider="codex",
        )
        no_effort = _event(
            "run-00000111-noeff", gate="PASS", artifact="a.md", provider="codex",
            closesRunIds=["run-00000110-revise"], evidence=[{"kind": "review", "ref": "x"}],
        )
        errors = self._validate([revise, no_effort])
        self.assertTrue(any("omits effort" in e for e in errors), errors)

    def test_unclassified_finding_is_not_user_waivable(self) -> None:
        revise = _event("run-00000120-revise", gate="REVISE", status="revise", artifact="a.md")
        waiver = _event(
            "run-00000121-waiver", gate="WAIVED:user", status="completed",
            closesRunIds=["run-00000120-revise"],
            evidence=[{"kind": "manual-check", "ref": "operator authorized"}],
        )
        errors = self._validate([revise, waiver])
        self.assertTrue(any("unclassified" in e and "(C5)" in e for e in errors), errors)

    def test_unsettled_launch_blocks_strict_mode(self) -> None:
        launch = _event("run-00000130-launch", eventKind="launch", status="running")
        errors = self._validate([launch], strict=True)
        self.assertTrue(any("unsettled launch" in e for e in errors), errors)
        errors = self._validate([launch], strict=False)
        self.assertEqual(errors, [], errors)

    def test_waiver_evidence_must_name_targets(self) -> None:
        # Sol impl-gate: unrelated authorization text is not authority — the
        # manual-check ref must NAME the exact runIds it waives.
        revise = _event("run-00000150-revise", gate="REVISE", status="revise",
                        artifact="a.md", findingClass="correctness")
        unbound = _event(
            "run-00000151-unbound", gate="WAIVED:user", status="completed",
            closesRunIds=["run-00000150-revise"],
            evidence=[{"kind": "manual-check", "ref": "unrelated checklist completed"}],
        )
        errors = self._validate([revise, unbound])
        self.assertTrue(any("target-bound" in e for e in errors), errors)

    def test_waiver_evidence_prefix_collision_fails(self) -> None:
        # Sol impl-gate r2: evidence naming run-X-extra must not authorize run-X.
        revise = _event("run-00000160-target", gate="REVISE", status="revise",
                        artifact="a.md", findingClass="correctness")
        prefixy = _event(
            "run-00000161-prefix", gate="WAIVED:user", status="completed",
            closesRunIds=["run-00000160-target"],
            evidence=[{"kind": "manual-check", "ref": "operator waives run-00000160-target-extra only"}],
        )
        errors = self._validate([revise, prefixy])
        self.assertTrue(any("target-bound" in e for e in errors), errors)

    def test_advisory_roles_cannot_close(self) -> None:
        # consultant is advisory-only (governance); brigade is a dispatch surface.
        revise = _event("run-00000140-revise", gate="REVISE", status="revise", artifact="a.md")
        for exec_role in ("consultant", "external-brigade", "main"):
            closer = _event(
                f"run-00000141-{exec_role[:6]}", gate="PASS", artifact="a.md",
                executionRole=exec_role,
                closesRunIds=["run-00000140-revise"], evidence=[{"kind": "review", "ref": "x"}],
            )
            errors = self._validate([revise, closer])
            self.assertTrue(
                any("reviewer-side" in e and "(C3)" in e for e in errors),
                (exec_role, errors),
            )

    # ---------- schema epoch ----------

    def test_v2_fields_on_v1_event_fail(self) -> None:
        v1 = _event("run-00000080-v1", schemaVersion=1, lane="architecture-deep")
        errors = self._validate([v1], strict=False)
        self.assertTrue(any("requires schemaVersion 2" in e for e in errors), errors)

    def test_v1_revise_does_not_trip_strict_mode(self) -> None:
        # Pre-existing v1 ledgers migrate by hand (fable minimal-slice gate); strict
        # open-REVISE applies to v2 events only.
        v1_revise = _event("run-00000090-v1rev", schemaVersion=1, gate="REVISE", status="revise")
        errors = self._validate([v1_revise], strict=True)
        self.assertEqual(errors, [], errors)


if __name__ == "__main__":
    unittest.main()


class ArtifactResolutionFixture(unittest.TestCase):
    """A review's artifact is usually a REPOSITORY file, not a copy inside the item.

    Live incident (2026-07-17): an adversarial reviewer returned `GATE: PASS` for
    `scripts/maintenance/cleanup.py`; the wrapper's terminal append was REJECTED with
    `artifact does not exist: scripts/maintenance/cleanup.py` because the validator
    resolved the artifact only against the work-item directory. The verdict was dropped
    and the obligation stayed open — the machinery silently refused to record the very
    event it exists to demand.
    """

    def _repo(self) -> tuple[Path, Path]:
        """A realistic layout: <root>/work-items/active/<item> plus a repo file."""
        import json

        root = Path(tempfile.mkdtemp())
        item = root / "work-items" / "active" / "2026-07-17-fixture"
        item.mkdir(parents=True)
        (item / "status.md").write_text(STATUS_MD, encoding="utf-8")
        (item / "design.md").write_text("work-item-local artifact\n", encoding="utf-8")
        engine = root / "scripts" / "maintenance" / "cleanup.py"
        engine.parent.mkdir(parents=True)
        engine.write_text("# repository artifact under review\n", encoding="utf-8")
        return root, item

    def _write_events(self, item: Path, events: list[dict]) -> None:
        import json

        with (item / "agent-runs.jsonl").open("w", encoding="utf-8") as fh:
            for e in events:
                fh.write(json.dumps(e) + "\n")

    def test_pass_closer_on_a_repository_artifact_is_recordable(self) -> None:
        root, item = self._repo()
        revise = _event(
            "run-repoart-revise",
            gate="REVISE",
            status="revise",
            artifact="scripts/maintenance/cleanup.py",
            lane="impl-adversarial",
            effort="high",
            provider="codex",
            findingClass="correctness",
        )
        closer = _event(
            "run-repoart-pass",
            gate="PASS",
            artifact="scripts/maintenance/cleanup.py",
            lane="impl-adversarial",
            effort="high",
            provider="codex",
            closesRunIds=["run-repoart-revise"],
            evidence=[{"kind": "review", "ref": ".scratch/x.out"}],
        )
        self._write_events(item, [revise, closer])

        errors = vws.validate_work_item(item)

        self.assertEqual(errors, [], f"repo-root artifact must resolve: {errors}")

    def test_work_item_local_artifact_still_resolves(self) -> None:
        root, item = self._repo()
        closer = _event(
            "run-localart-pass",
            gate="PASS",
            artifact="design.md",
            lane="architecture-deep",
            effort="xhigh",
            provider="codex",
            evidence=[{"kind": "review", "ref": ".scratch/x.out"}],
        )
        self._write_events(item, [closer])

        errors = vws.validate_work_item(item)

        self.assertEqual(errors, [], f"work-item-local artifact must still resolve: {errors}")

    def test_missing_artifact_still_fails(self) -> None:
        root, item = self._repo()
        closer = _event(
            "run-noart-pass",
            gate="PASS",
            artifact="scripts/maintenance/does-not-exist.py",
            lane="impl-adversarial",
            effort="high",
            provider="codex",
            evidence=[{"kind": "review", "ref": ".scratch/x.out"}],
        )
        self._write_events(item, [closer])

        errors = vws.validate_work_item(item)

        self.assertTrue(
            any("artifact does not exist" in e for e in errors),
            f"a genuinely missing artifact must still fail: {errors}",
        )

    def test_artifact_escaping_both_roots_fails(self) -> None:
        root, item = self._repo()
        closer = _event(
            "run-escape-pass",
            gate="PASS",
            artifact="../../../../etc/passwd",
            lane="impl-adversarial",
            effort="high",
            provider="codex",
            evidence=[{"kind": "review", "ref": ".scratch/x.out"}],
        )
        self._write_events(item, [closer])

        errors = vws.validate_work_item(item)

        self.assertTrue(errors, "an artifact escaping the repository must fail")
