"""Frozen coordinator-only repository-cleanup contract."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPINE = ROOT / "shared" / "AGENTS.shared.md"
REFERENCE = ROOT / "shared" / "references" / "repository-cleanup.md"
CODEX_SKILL = ROOT / "src.codex" / "skills" / "repo-cleanup" / "SKILL.md"
CLAUDE_SKILL = ROOT / "src.claude" / "skills" / "repo-cleanup" / "SKILL.md"
CODEX_INTERFACE = (
    ROOT / "src.codex" / "skills" / "repo-cleanup" / "agents" / "openai.yaml"
)
TURN_ANCHOR = (
    ROOT / "scripts" / "universal-hooks" / "scripts" / "turn-anchor-reminder.py"
)


def _body(path: Path) -> str:
    data = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    parts = data.split("\n---\n", 1)
    assert len(parts) == 2, f"unterminated frontmatter: {path}"
    return parts[1]


def _common_skills() -> tuple[str, ...]:
    text = SPINE.read_text(encoding="utf-8")
    match = re.search(r"^## Common skills\b.*?\bSet:\s*(.+?)\.", text, re.S | re.M)
    assert match, "shared common-skill registry is missing"
    return tuple(re.findall(r"`\$([a-z][a-z0-9-]+)`", match.group(1)))


def test_repo_cleanup_is_one_common_skill_with_byte_equivalent_provider_semantics() -> None:
    assert "repo-cleanup" in _common_skills()
    assert CODEX_SKILL.is_file()
    assert CLAUDE_SKILL.is_file()
    assert CODEX_INTERFACE.is_file()
    assert _body(CODEX_SKILL) == _body(CLAUDE_SKILL)

    codex_members = {
        path.relative_to(CODEX_SKILL.parent).as_posix()
        for path in CODEX_SKILL.parent.rglob("*")
        if path.is_file()
    }
    claude_members = {
        path.relative_to(CLAUDE_SKILL.parent).as_posix()
        for path in CLAUDE_SKILL.parent.rglob("*")
        if path.is_file()
    }
    assert codex_members == {"SKILL.md", "agents/openai.yaml"}
    assert claude_members == {"SKILL.md"}


def test_repo_cleanup_contract_is_transient_coordinator_only() -> None:
    body = _body(CODEX_SKILL)
    assert REFERENCE.is_file()
    for required in (
        "scan -> classify -> route -> recheck",
        "RepoCleanupReportV1",
        "ResourceRowV1",
        "PredicateRowV1",
        "current invocation",
        "never persisted or reloaded",
        "never authorizes mutation",
        "never deletes, moves, terminates, unlocks, rewrites, commits, pushes, or archives",
        "REVISE:cleanup-capacity-unresolved",
    ):
        assert required in body


def test_work_items_selection_requires_an_exhaustive_immediate_child_census() -> None:
    for path in (CODEX_SKILL, CLAUDE_SKILL, REFERENCE):
        text = path.read_text(encoding="utf-8")
        for required in (
            "when `work-items/` is selected",
            "every immediate child exactly once",
            "`category | derived | repository-local exception | unknown`",
            "audit `PASS` does not satisfy this census",
            "`unknown` remains preserved",
            "yields `REVISE`",
        ):
            assert required.casefold() in text.casefold(), (
                f"{path.relative_to(ROOT)} missing {required!r}"
            )


def test_scratch_is_temporary_until_canonical_results_are_promoted() -> None:
    spine = SPINE.read_text(encoding="utf-8")
    for required in (
        "`.scratch/` is disposable task storage",
        "before completion, canonically promote load-bearing results",
        "then remove owned temp state",
        "Never delete unfinished/foreign/ambiguous/host-denied state",
    ):
        assert required in spine

    for path in (CODEX_SKILL, CLAUDE_SKILL):
        text = path.read_text(encoding="utf-8")
        for required in (
            "canonical pointer does not make scratch archival",
            "promote required results before task completion",
            "then settle owned temporary scratch",
        ):
            assert required in text, f"{path.relative_to(ROOT)} missing {required!r}"

    for relative in (
        "src.codex/skills/lead/SKILL.md",
        "src.claude/skills/lead/SKILL.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for required in (
            "`retain` is transitional, not archival",
            "promotes required results before task completion",
            "later settles owned temporary scratch",
        ):
            assert required.casefold() in text.casefold(), (
                f"{relative} missing {required!r}"
            )

    for relative in (
        "src.codex/skills/manual-repo-transfer/SKILL.md",
        "src.claude/skills/manual-repo-transfer/SKILL.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for required in (
            "promote required scratch results to canonical artifacts",
            "raw scratch only while recovery requires it",
        ):
            assert required.casefold() in text.casefold(), (
                f"{relative} missing {required!r}"
            )


def test_host_refusal_preserves_target_without_bypass_or_false_pass() -> None:
    surfaces = (CODEX_SKILL, CLAUDE_SKILL, REFERENCE)
    required = (
        "host refuses a validated owner action before execution",
        "disposition `preserved`",
        "redacted refusal reason",
        "pre-action and post-refusal settlement probe results",
        "no alternate shell, API, provider, command shape, retry, or allow-rule",
        "same validated action",
        "root main conversation and its existing current work-item",
        "independent non-overlapping work continues",
        "dependent zero-residue predicates remain `fail`",
    )
    for path in surfaces:
        text = path.read_text(encoding="utf-8")
        for fragment in required:
            assert fragment.casefold() in text.casefold(), (
                f"{path.relative_to(ROOT)} missing {fragment!r}"
            )

    body = _body(CODEX_SKILL)
    assert "owner-action-refused" not in body
    assert "new refusal disposition" not in body


def test_repo_cleanup_fixed_hysteresis_and_report_rows_are_complete() -> None:
    body = _body(CODEX_SKILL)
    for boundary in (
        "freeRatio >= 0.20",
        "freeRatio < 0.20",
        "freeRatio >= 0.30",
        "Exactly `0.20` does not trigger cleanup",
        "Exactly `0.30` satisfies the preferred target",
        "cleanupCandidateBytes",
        "volumeCapacityBytes",
        "freeCapacityBytes",
        "ephemeral-volume-exempt",
    ):
        assert boundary in body

    for predicate in (
        "WS-CLASSIFIED",
        "WS-SELF-RESIDUE-ZERO",
        "WS-PREEXISTING-UNTOUCHED",
        "WS-EPHEMERAL-EXEMPT-VALID",
        "WI-EXISTING-AUDIT",
        "WI-OWNED-RESIDUE-ZERO",
        "GIT-CLASSIFIED",
        "GIT-TEMP-RESOURCES-ZERO",
        "XFER-ORDER",
        "XFER-TRUSTED-VERIFY",
        "XFER-POST-CLASSIFIED",
    ):
        assert predicate in body


def test_lead_and_receiving_contracts_fail_closed_on_self_residue() -> None:
    for relative in (
        "src.codex/skills/lead/SKILL.md",
        "src.claude/skills/lead/SKILL.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "RepoCleanupReportV1" in text
        assert "status `PASS`" in text
        assert "REVISE:self-residue" in text

    for relative in (
        "src.codex/skills/lead/subagent-contracts.md",
        "src.claude/agents/contracts/subagent-contracts.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "ResourceRowV1" in text
        assert "creator/adopter role + run" in text
        assert "settlement probe and current result" in text
        assert "Dead/superseded code disposition" in text


def test_lead_intermediate_acceptance_uses_producer_owned_resource_echo() -> None:
    for relative in (
        "src.codex/skills/lead/SKILL.md",
        "src.claude/skills/lead/SKILL.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        acceptance = text.split(
            "Lead acceptance is a mechanical completeness gate:", 1
        )[1].split("When an accepted artifact asserts a root cause", 1)[0]
        for bounded_control in (
            "producing artifact's current receiving-side echo",
            "`Cleanup disposition`",
            "`ResourceRowV1`",
            "no selected owned resources",
            "without a fresh repository-wide `RepoCleanupReportV1`",
            "the label alone is not evidence",
            "unsettled owned resources",
            "`none` claim contradicted by a row or current evidence",
            "`REVISE:self-residue`",
        ):
            assert bounded_control in acceptance

        for full_cleanup_trigger in (
            "is required only when",
            "`$repo-cleanup` is selected",
            "a transfer contract requires it",
            "concrete evidence makes the bounded owner inventory insufficient",
        ):
            assert full_cleanup_trigger in acceptance

        for preserved_full_report_control in (
            "current-invocation `RepoCleanupReportV1` with status `PASS`",
            "same physical repository identity and `HEAD`/unborn state",
            "missing, stale, incomplete, null, non-`PASS`, or non-zero "
            "residue/unclassified rows",
            "Valid `ephemeral-volume-exempt` rows",
            "never authorizes cleanup or substitutes for an owner verdict",
        ):
            assert preserved_full_report_control in acceptance

        assert (
            "For every Lead-managed acceptance, require one complete "
            "current-invocation `RepoCleanupReportV1`"
        ) not in acceptance


def test_transfer_receiving_contract_enforces_one_ordered_cleanup_chain() -> None:
    expected = (
        "cleanup PASS or qualifying deferred residue accounted -> final inventory -> bundle -> trusted verify -> "
        "post-transfer classification"
    )
    for relative in (
        "src.codex/skills/manual-repo-transfer/SKILL.md",
        "src.claude/skills/manual-repo-transfer/SKILL.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert expected in text
        assert "current-invocation" in text
        assert "RepoCleanupReportV1" in text
        assert "does not run cleanup again" in text


def test_turn_anchor_emits_direct_root_no_self_residue_invariant() -> None:
    result = subprocess.run(
        [sys.executable, str(TURN_ANCHOR)],
        cwd=ROOT,
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "no-self-residue" in context
    assert "completion, commit, push, or handoff" in context
    assert "pre-existing user state" in context


def test_turn_anchor_uses_the_universal_policy_owner() -> None:
    policy_path = (
        ROOT / "scripts" / "universal-hooks" / "scripts" / "mcp_continuity_policy.py"
    )
    spec = importlib.util.spec_from_file_location("repo_cleanup_anchor_policy", policy_path)
    assert spec is not None and spec.loader is not None
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    emitted = subprocess.run(
        [sys.executable, str(TURN_ANCHOR)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    context = json.loads(emitted.stdout)["hookSpecificOutput"]["additionalContext"]
    assert context == policy.TURN_ANCHOR_CONTEXT


def test_installer_accepts_only_the_exact_immediate_predecessor_skill_trees() -> None:
    installer_path = ROOT / "scripts" / "production_installer.py"
    spec = importlib.util.spec_from_file_location("repo_cleanup_installer", installer_path)
    assert spec is not None and spec.loader is not None
    installer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = installer
    try:
        spec.loader.exec_module(installer)
    finally:
        sys.modules.pop(spec.name, None)

    lead_prior = "87df0dfbef0bf1ae336ef5b26fa60e3a155e7519d2d7494818ce592a37b52a32"
    transfer_prior = "cdc90d427cc593ee7b7212dd0ddeacbb13dc7474525b493bd8950318bbc3d92f"
    assert lead_prior in installer.GLOBAL_LEAD_ACCEPTED_PRIOR_TREE_SHA256
    assert transfer_prior in installer.ADDITIONAL_STOCK_SKILL_ACCEPTED_PRIOR_TREE_SHA256[
        "manual-repo-transfer"
    ]
    assert ("0" + lead_prior[1:]) not in installer.GLOBAL_LEAD_ACCEPTED_PRIOR_TREE_SHA256
    assert (
        "0" + transfer_prior[1:]
    ) not in installer.ADDITIONAL_STOCK_SKILL_ACCEPTED_PRIOR_TREE_SHA256[
        "manual-repo-transfer"
    ]
