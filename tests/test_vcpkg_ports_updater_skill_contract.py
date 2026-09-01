"""Codex vcpkg overlay-updater skill and create-only install contract."""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "src.codex" / "skills" / "vcpkg-ports-updater"


def _load_installer():
    path = ROOT / "scripts" / "production_installer.py"
    spec = importlib.util.spec_from_file_location("vcpkg_skill_installer", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def test_vcpkg_ports_updater_has_the_common_general_overlay_contract() -> None:
    files = {
        path.relative_to(SKILL_ROOT).as_posix()
        for path in SKILL_ROOT.rglob("*")
        if path.is_file()
    }
    assert files == {
        "SKILL.md",
        "agents/openai.yaml",
        "references/upstream-sync.md",
    }
    claude_root = ROOT / "src.claude" / "skills" / "vcpkg-ports-updater"
    claude_files = {
        path.relative_to(claude_root).as_posix()
        for path in claude_root.rglob("*")
        if path.is_file()
    }
    assert claude_files == {"SKILL.md", "references/upstream-sync.md"}
    assert (claude_root / "SKILL.md").read_bytes() == (SKILL_ROOT / "SKILL.md").read_bytes()
    assert (claude_root / "references" / "upstream-sync.md").read_bytes() == (
        SKILL_ROOT / "references" / "upstream-sync.md"
    ).read_bytes()

    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    reference = (SKILL_ROOT / "references" / "upstream-sync.md").read_text(
        encoding="utf-8"
    )
    for contract in (
        "named overlay roots/tiers",
        "read-only inventory",
        "current",
        "update-candidate",
        "unknown",
        "stale-overlay-candidate",
        "establish ancestry",
        "manifest and delegated portfile",
    ):
        assert contract in skill
    assert "manifest/portfile version split" in skill
    assert "Builtin vcpkg checkout and `microsoft/vcpkg` history" in reference


def test_new_skill_install_is_create_only_idempotent_and_collision_safe(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    target = tmp_path / "target"
    target.mkdir()
    skills_root = target / ".agents" / "skills"
    owner = installer._CreateOnlyMutablePath(
        target,
        installer._InstallTransaction([], enabled=False),
        dry_run=False,
    )

    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        selected = next(
            skill for skill in plan.skills if skill.name == "vcpkg-ports-updater"
        )
        assert selected.installed_digest is None
        assert selected.accepted_prior is None
        installer._apply_canonical_skills_plan(plan, skills_root, owner, root=ROOT)
    finally:
        installer._discard_canonical_skills_plan(plan)

    installed = skills_root / "vcpkg-ports-updater"
    expected = {
        path.relative_to(SKILL_ROOT): path.read_bytes()
        for path in SKILL_ROOT.rglob("*")
        if path.is_file()
    }
    assert {
        path.relative_to(installed): path.read_bytes()
        for path in installed.rglob("*")
        if path.is_file()
    } == expected

    before_noop = {
        path.relative_to(skills_root): path.read_bytes()
        for path in skills_root.rglob("*")
        if path.is_file()
    }
    current_plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", skills_root, root=ROOT
    )
    try:
        selected = next(
            skill
            for skill in current_plan.skills
            if skill.name == "vcpkg-ports-updater"
        )
        assert selected.installed_digest == selected.source_digest
        assert selected.accepted_prior is None
        installer._apply_canonical_skills_plan(
            current_plan, skills_root, owner, root=ROOT
        )
    finally:
        installer._discard_canonical_skills_plan(current_plan)
    assert {
        path.relative_to(skills_root): path.read_bytes()
        for path in skills_root.rglob("*")
        if path.is_file()
    } == before_noop

    with (installed / "SKILL.md").open("ab") as stream:
        stream.write(b"one byte of user drift\n")
    with pytest.raises(
        ValueError, match="E_ACCEPTED_PRIOR_COLLISION: vcpkg-ports-updater"
    ):
        installer._preflight_canonical_skills(
            ROOT / "src.codex" / "skills", skills_root, root=ROOT
        )


def test_claude_installer_projection_is_create_only_idempotent_and_collision_safe(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    target = tmp_path / "target"
    target.mkdir()
    canonical_target = target / ".agents" / "skills"
    projection_root = target / ".claude" / "skills"
    shutil.copytree(SKILL_ROOT, canonical_target / "vcpkg-ports-updater")
    owner = installer._CreateOnlyMutablePath(
        target,
        installer._InstallTransaction([], enabled=False),
        dry_run=False,
    )
    plan = installer._preflight_claude_skill_projections(
        ROOT / "src.codex" / "skills",
        ROOT / "src.claude" / "skills",
        canonical_target,
        projection_root,
    )
    selected = next(item for item in plan if item.name == "vcpkg-ports-updater")
    assert selected.action == "create"
    assert selected.canonical_target == canonical_target / "vcpkg-ports-updater"
    assert selected.historical_digest is None
    installer._apply_claude_skill_projection_plan(
        (selected,), ROOT / "src.codex" / "skills", projection_root, owner
    )

    current = installer._preflight_claude_skill_projections(
        ROOT / "src.codex" / "skills",
        ROOT / "src.claude" / "skills",
        canonical_target,
        projection_root,
    )
    replay = next(item for item in current if item.name == "vcpkg-ports-updater")
    assert replay.action == "current"
    installer._apply_claude_skill_projection_plan(
        (replay,), ROOT / "src.codex" / "skills", projection_root, owner
    )

    projection = projection_root / "vcpkg-ports-updater"
    projection.unlink()
    shutil.copytree(SKILL_ROOT, projection)
    with (projection / "SKILL.md").open("ab") as stream:
        stream.write(b"one byte of projection drift\n")
    with pytest.raises(
        ValueError,
        match="E_CREATE_ONLY_PROJECTION_COLLISION: vcpkg-ports-updater",
    ):
        installer._preflight_claude_skill_projections(
            ROOT / "src.codex" / "skills",
            ROOT / "src.claude" / "skills",
            canonical_target,
            projection_root,
        )
