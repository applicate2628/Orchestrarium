"""Frozen coordinator-only repository-cleanup contract."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


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
CANONICAL_PRIOR = (
    ROOT / "tests/fixtures/canonical-skill-priors"
    / "8bd58995a10966370cf3df1f04ed63dd94ca529d"
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


def test_repo_cleanup_has_one_current_body_and_a_frozen_migration_source() -> None:
    assert "repo-cleanup" in _common_skills()
    assert CODEX_SKILL.is_file()
    assert CLAUDE_SKILL.is_file()
    assert CODEX_INTERFACE.is_file()
    assert hashlib.sha256(CLAUDE_SKILL.read_bytes()).hexdigest() == "06fe776be7a9c75ec5491fdf8a54e16c65e2586ab0f04ec972d3501cae55c060"
    assert _body(CODEX_SKILL) != _body(CLAUDE_SKILL)

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
        "then settle owned temp state",
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
        "Artifact disposition and project hygiene",
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
            "unsettled residue/unclassified rows",
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


def test_action_local_blockers_and_final_transfer_classification() -> None:
    operating_model = (ROOT / "shared/references/subagent-operating-model.md").read_text(
        encoding="utf-8"
    )
    assert "bind each prerequisite to the exact action it prevents" in operating_model
    assert "independently ready admitted work continues" in operating_model

    for relative in (
        "src.codex/skills/lead/SKILL.md",
        "src.claude/skills/lead/SKILL.md",
    ):
        lead = (ROOT / relative).read_text(encoding="utf-8")
        assert "grouped gate is not a global stop" in lead
        assert "independently ready admitted action" in lead

    cleanup = REFERENCE.read_text(encoding="utf-8")
    assert "selected work-item and owned bug-inbox obligations" in cleanup
    assert "byte-verified ZIP is only a provisional recovery snapshot" in cleanup
    assert "explicit direct transfer without cleanup" in cleanup

    for relative in (
        "src.codex/skills/manual-repo-transfer/SKILL.md",
        "src.claude/skills/manual-repo-transfer/SKILL.md",
    ):
        transfer = (ROOT / relative).read_text(encoding="utf-8")
        assert "provisional recovery snapshot, not final handoff" in transfer
        assert "direct transfer without cleanup" in transfer


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


def test_general_disposition_moves_disposable_artifacts_to_purgable_trash_first() -> None:
    spine = SPINE.read_text(encoding="utf-8")
    paragraph = next(line for line in spine.splitlines()
                     if line.startswith("- **Artifact disposition and project hygiene:**"))
    for required in (
        "Trash-first",
        "as soon as it is confirmed unnecessary",
        "do not wait for a failed deletion",
        "safe to empty completely",
        "no required recovery or acceptance evidence depends on trash",
        "only from trash",
        "Agents never automatically purge manual-deletion trash",
        "Unknown, foreign, ambiguous, valuable, active or prohibited material stays preserved",
        "Never bypass a denial",
        "a move grants no purge permission",
        "does not rewrite internal atomic replacement, transaction rollback or live-resource release contracts",
        "no-overwrite semantics",
        "source absence",
        "exact source/destination authority",
    ):
        assert required in paragraph
    for obsolete in (
        "First establish the actual deletion outcome",
        "normal permitted resolution cannot complete deletion",
        "A first failure or refusal alone does not select trash",
    ):
        assert obsolete not in paragraph


def test_cleanup_consumers_do_not_restore_delete_first_or_unsafe_trash() -> None:
    for path in (CODEX_SKILL, REFERENCE):
        text = path.read_text(encoding="utf-8")
        assert "trash-first" in text
        assert "attempted-deletion fallback" not in text
        assert "manual quarantine" not in text
        assert "quarantine prepared; manual deletion pending" not in text
    text = CODEX_SKILL.read_text(encoding="utf-8")
    assert "only from trash" in text
    assert "disposable material already in trash" in text
    assert "owner may delete only classified disposable material" not in text


def test_russian_hygiene_mirror_preserves_trash_first_guarantees() -> None:
    text = (ROOT / "shared/references/ru/repository-source-hygiene.md").read_text(encoding="utf-8")
    for phrase in ('без предварительной попытки удаления', 'можно полностью очистить вручную', 'не зависят', 'только из trash'):
        assert phrase in text
    assert "delete it; git history preserves the file" not in text


def _load_source_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


@pytest.mark.parametrize("provider", ("codex", "claude"))
@pytest.mark.parametrize("mutation", (None, "canonical", "historical", "both", "missing"))
def test_cleanup_validator_binds_current_and_historical_sources(
    tmp_path: Path, provider: str, mutation: str | None,
) -> None:
    """Neither a unilateral edit nor identical tampering restores false parity."""
    relative = (
        "src.codex/skills/lead/scripts/validate-skill-pack.py"
        if provider == "codex" else "src.claude/agents/scripts/validate-skill-pack.py"
    )
    adapter = _load_source_module(ROOT / relative, f"cleanup_validator_{provider}")
    root = tmp_path / "repo"
    for source in (SPINE, ROOT / "src.codex/AGENTS.codex.md", CODEX_SKILL, CLAUDE_SKILL):
        target = root / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    (root / "src.codex/skills/lead/scripts").mkdir(parents=True)
    (root / "src.claude/agents/scripts").mkdir(parents=True)
    canonical = root / CODEX_SKILL.relative_to(ROOT)
    historical = root / CLAUDE_SKILL.relative_to(ROOT)
    if mutation == "canonical":
        canonical.write_bytes(canonical.read_bytes() + b"\nfixture body drift\n")
    elif mutation == "historical":
        historical.write_bytes(historical.read_bytes() + b"\nfixture body drift\n")
    elif mutation == "both":
        canonical.write_bytes(b"---\nname: repo-cleanup\ndescription: fixture\n---\nunapproved\n")
        historical.write_bytes(canonical.read_bytes())
    elif mutation == "missing":
        canonical.rename(canonical.with_suffix(".missing"))
    actions = tuple(
        (scope, tuple(action for action in group if any("repo-cleanup" in str(arg) for arg in action)))
        for scope, group in adapter.ACTIONS
    )
    runtime = adapter._ENGINE
    layout = runtime.detect_layout(root / relative, provider, root)
    assert layout.skills == root / "src.codex/skills"
    selected = tuple(runtime._applicable_actions(actions, layout))
    assert len(selected) == 2
    result = runtime.validate_pack(
        script=root / relative, provider=provider, actions=actions, root=root,
        maintainer_only_shared_reference_names=frozenset(),
        utility_skills=frozenset(), curated_role_skills=frozenset(),
    )
    assert result.errors == (0 if mutation is None else 2 if mutation == "both" else 1)
    assert result.warnings == 0


@pytest.mark.parametrize("mutation", (None, "installed-history", "canonical-after-plan"))
def test_cleanup_projection_preserves_historical_migration_binding(
    tmp_path: Path, mutation: str | None,
) -> None:
    """Read-only preflight: no native installation or lifecycle bypass."""
    installer = _load_source_module(
        ROOT / "scripts/production_installer.py", "cleanup_projection_installer"
    )
    current_source = tmp_path / "current-source"
    historical_source = tmp_path / "historical-source"
    target = tmp_path / "target"
    canonical_target = target / ".agents/skills"
    projection_root = target / ".claude/skills"
    shutil.copytree(CODEX_SKILL.parent, current_source / "repo-cleanup")
    shutil.copytree(CLAUDE_SKILL.parent, historical_source / "repo-cleanup")
    installed = projection_root / "repo-cleanup"
    shutil.copytree(CLAUDE_SKILL.parent, installed)
    if mutation == "installed-history":
        (installed / "SKILL.md").write_bytes(b"user-owned changed skill\n")
        with pytest.raises(ValueError, match="E_CREATE_ONLY_PROJECTION_COLLISION: repo-cleanup"):
            installer._preflight_claude_skill_projections(
                current_source, historical_source, canonical_target, projection_root,
            )
        assert (installed / "SKILL.md").read_bytes() == b"user-owned changed skill\n"
        return
    before = (installed / "SKILL.md").read_bytes()
    plan = installer._preflight_claude_skill_projections(
        current_source, historical_source, canonical_target, projection_root,
    )
    assert len(plan) == 1
    item = plan[0]
    assert item.action == "migrate"
    assert item.canonical_target == canonical_target / "repo-cleanup"
    assert item.canonical_digest == installer._tree_sha256(current_source / "repo-cleanup")
    assert item.historical_digest == installer._tree_sha256(historical_source / "repo-cleanup")
    assert item.historical_digest != item.canonical_digest
    if mutation == "canonical-after-plan":
        (current_source / "repo-cleanup/SKILL.md").write_bytes(b"source drift\n")
        with pytest.raises(ValueError, match="E_CREATE_ONLY_PROJECTION_COLLISION"):
            installer._assert_claude_skill_projection_plan_current(
                plan, current_source, projection_root,
            )
    else:
        installer._assert_claude_skill_projection_plan_current(plan, current_source, projection_root)
    assert (installed / "SKILL.md").read_bytes() == before
    assert not canonical_target.exists()


@pytest.mark.parametrize("provider", ("codex", "claude"))
@pytest.mark.parametrize("historical_body", (False, True))
def test_installed_cleanup_validator_requires_current_body_without_source_tree(
    tmp_path: Path, provider: str, historical_body: bool,
) -> None:
    relative = (
        "src.codex/skills/lead/scripts/validate-skill-pack.py"
        if provider == "codex" else "src.claude/agents/scripts/validate-skill-pack.py"
    )
    adapter = _load_source_module(ROOT / relative, f"installed_cleanup_{provider}")
    root = tmp_path / "installed"
    skills = root / (".agents/skills" if provider == "codex" else ".claude/skills")
    scripts = skills / "lead/scripts" if provider == "codex" else root / ".claude/agents/scripts"
    scripts.mkdir(parents=True)
    agents = root / ("AGENTS.md" if provider == "codex" else ".claude/AGENTS.md")
    agents.write_text("fixture governance\n", encoding="utf-8")
    skill = skills / "repo-cleanup/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_bytes((CLAUDE_SKILL if historical_body else CODEX_SKILL).read_bytes())
    actions = tuple(
        (scope, tuple(action for action in group if any("repo-cleanup" in str(arg) for arg in action)))
        for scope, group in adapter.ACTIONS
    )
    runtime = adapter._ENGINE
    layout = runtime.detect_layout(scripts / "validate-skill-pack.py", provider, root)
    assert not layout.dev_repo
    assert len(tuple(runtime._applicable_actions(actions, layout))) == 1
    result = runtime.validate_pack(
        script=scripts / "validate-skill-pack.py", provider=provider, actions=actions, root=root,
        maintainer_only_shared_reference_names=frozenset(),
        utility_skills=frozenset(), curated_role_skills=frozenset(),
    )
    assert result.errors == int(historical_body)
    assert result.warnings == 0


def test_cleanup_stock_upgrade_uses_one_exact_member_manifest_witness() -> None:
    installer = _load_source_module(
        ROOT / "scripts/production_installer.py", "cleanup_stock_installer"
    )
    prior = CANONICAL_PRIOR / "repo-cleanup"
    manifest = json.loads((CANONICAL_PRIOR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    assert manifest["baseline"] == CANONICAL_PRIOR.name
    assert manifest["files"] == {
        "repo-cleanup/SKILL.md": "06fe776be7a9c75ec5491fdf8a54e16c65e2586ab0f04ec972d3501cae55c060",
        "repo-cleanup/agents/openai.yaml": "f176678edd9df4f93335d3e90557f84f040b332318bd8296b2c7f87022867185",
    }
    assert {
        path.relative_to(CANONICAL_PRIOR).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in prior.rglob("*") if path.is_file()
    } == manifest["files"]
    legacy = installer._legacy_tree_sha256(prior, ignore_runtime_cache=True)
    strong = installer._tree_sha256(prior, ignore_runtime_cache=True)
    assert legacy == "36ca45866892cab034addd9eb69a849fc1dcd82e473846093bd4e38107736b24"
    assert strong == "8f56fb527cb1d92527b1fc1f4976508dbf1115d85a340bdd57322da6e1985e57"
    assert installer.ADDITIONAL_STOCK_SKILL_ACCEPTED_PRIOR_TREE_SHA256["repo-cleanup"] == {legacy: strong}
    assert installer._legacy_factory_identity_v2("repo-cleanup", legacy) == strong
    assert installer._legacy_factory_identity_v2("repo-cleanup", "0" + legacy[1:]) is None


@pytest.mark.parametrize("mutation", (None, "body", "extra-file"))
def test_cleanup_project_upgrade_planning_only_stops_at_native_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str | None,
) -> None:
    """Exercise the real planner without claiming native update qualification."""
    installer = _load_source_module(
        ROOT / "scripts/production_installer.py", "cleanup_upgrade_planner"
    )
    source = tmp_path / "source"
    shutil.copytree(ROOT / "src.codex/skills/lead", source / "lead")
    shutil.copytree(CODEX_SKILL.parent, source / "repo-cleanup")
    target = tmp_path / "project/.agents/skills"
    installed = target / "repo-cleanup"
    shutil.copytree(CANONICAL_PRIOR / "repo-cleanup", installed)
    if mutation == "body":
        (installed / "SKILL.md").write_bytes(b"user-owned body\n")
    elif mutation == "extra-file":
        (installed / "user.txt").write_bytes(b"user-owned extra\n")
    def snapshot():
        return {
            path.relative_to(installed): (
                path.stat().st_dev, path.stat().st_ino,
                path.read_bytes() if path.is_file() else None,
            )
            for path in (installed, *installed.rglob("*"))
        }

    before = snapshot()
    observed = []

    class NativeQualificationPending(Exception):
        pass

    def stop_before_native_probe(plan, planned_target):
        observed.append(plan)
        assert planned_target == target
        raise NativeQualificationPending

    monkeypatch.setattr(installer, "_preflight_directory_move_capabilities", stop_before_native_probe)
    if mutation is None:
        with pytest.raises(NativeQualificationPending):
            installer._preflight_canonical_skills(source, target, root=ROOT, global_install=False)
        assert len(observed) == 1
        skill = next(item for item in observed[0].skills if item.name == "repo-cleanup")
        assert skill.accepted_prior == "8f56fb527cb1d92527b1fc1f4976508dbf1115d85a340bdd57322da6e1985e57"
        assert skill.installed_digest == skill.accepted_prior
        assert skill.source_digest == installer._tree_sha256(source / "repo-cleanup", ignore_runtime_cache=True)
        assert skill.source_digest != skill.accepted_prior
    else:
        with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: repo-cleanup"):
            installer._preflight_canonical_skills(source, target, root=ROOT, global_install=False)
        assert observed == []
    assert snapshot() == before
    assert sorted(path.name for path in target.iterdir()) == ["repo-cleanup"]
