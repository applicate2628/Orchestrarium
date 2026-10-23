from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "production_installer.py"


def load_installer():
    spec = importlib.util.spec_from_file_location(
        "production_installer_legacy_skill_compatibility", INSTALLER
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_python(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(path), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def launch_flags_probe(validator: Path) -> subprocess.CompletedProcess[str]:
    source = """
import importlib.util
import sys
from pathlib import Path
path = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("installed_validator_probe", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
print(module.validate_launch_profile("codex", [
    "--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=high",
    "--sandbox", "read-only",
]))
try:
    module.validate_launch_profile("codex", ["--prompt"])
except ValueError as exc:
    print(f"INVALID: {exc}")
else:
    raise SystemExit("invalid launch flags were accepted")
"""
    return subprocess.run(
        [sys.executable, "-B", "-c", source, str(validator)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_codex_install_keeps_legacy_lead_entrypoint_on_canonical_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer = load_installer()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    (home / ".codex").mkdir()
    legacy_skills = home / ".codex" / "skills"
    legacy_store = tmp_path / "legacy-skills-store"
    legacy_store.mkdir()
    installer._create_directory_projection(
        legacy_store, legacy_skills, prefer_junction=True
    )
    root_identity = installer._CreateOnlyMutablePath._identity(legacy_skills)
    vendor_marker = legacy_skills / "vendor-extension" / "marker.txt"
    vendor_marker.parent.mkdir(parents=True)
    vendor_marker.write_text("preserve vendor skill\n", encoding="utf-8")

    result = installer.install(
        "codex", ["--global", "--no-hypothesis-hook"]
    )

    assert result == 0
    canonical_lead = home / ".agents" / "skills" / "lead"
    legacy_lead = legacy_skills / "lead"
    assert canonical_lead.is_dir()
    assert legacy_lead.is_dir()
    assert os.path.samefile(legacy_skills, legacy_store)
    assert installer._CreateOnlyMutablePath._identity(legacy_skills) == root_identity
    canonical_names = sorted(
        path.name for path in canonical_lead.parent.iterdir() if path.is_dir()
    )
    assert canonical_names
    for name in canonical_names:
        assert os.path.samefile(
            legacy_skills / name, canonical_lead.parent / name
        )
    assert vendor_marker.read_text(encoding="utf-8") == "preserve vendor skill\n"

    for label, lead in (("canonical", canonical_lead), ("legacy", legacy_lead)):
        project = tmp_path / f"{label}-project"
        (project / "work-items").mkdir(parents=True)
        refreshed = run_python(
            lead / "scripts" / "mutate-work-item.py",
            "refresh",
            "--root",
            str(project),
        )
        assert refreshed.returncode == 0, (refreshed.stdout, refreshed.stderr)
        audited = run_python(
            lead / "scripts" / "mutate-work-item.py",
            "audit",
            "--root",
            str(project),
        )
        assert audited.returncode == 0, (audited.stdout, audited.stderr)
        assert "AUDIT: PASS" in audited.stdout
        assert "Traceback" not in audited.stdout + audited.stderr

        invalid_registry = project / "work-items" / "decisions" / "invalid.md"
        invalid_registry.parent.mkdir()
        invalid_registry.write_text(
            "status: dropped\n"
            "Terminal-at: 2026-09-11T00:00:00Z\n"
            "Rationale: synthetic invalid current record\n"
            "Evidence: compatibility regression\n",
            encoding="utf-8",
        )
        invalid_audit = run_python(
            lead / "scripts" / "mutate-work-item.py",
            "audit",
            "--root",
            str(project),
        )
        assert invalid_audit.returncode == 1
        assert "WI-CATEGORY-TERMINAL-IN-CURRENT" in invalid_audit.stdout
        assert "Traceback" not in invalid_audit.stdout + invalid_audit.stderr

        probed = launch_flags_probe(
            lead / "scripts" / "validate-work-item-state.py"
        )
        assert probed.returncode == 0, (probed.stdout, probed.stderr)
        assert "gpt-5.6-sol" in probed.stdout
        assert "INVALID: invalid launch flags" in probed.stdout
        assert "Traceback" not in probed.stdout + probed.stderr


def tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def configured_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[object, Path, Path]:
    installer = load_installer()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    legacy_skills = home / ".codex" / "skills"
    return installer, home, legacy_skills


def test_legacy_same_name_collision_preserves_tree_and_canonical_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer, home, legacy_skills = configured_home(tmp_path, monkeypatch)
    legacy_lead = legacy_skills / "lead"
    legacy_lead.mkdir(parents=True)
    marker = legacy_lead / "custom.txt"
    marker.write_text("ambiguous custom lead\n", encoding="utf-8")
    vendor = legacy_skills / "vendor-extension" / "marker.txt"
    vendor.parent.mkdir()
    vendor.write_text("vendor\n", encoding="utf-8")

    result = installer.install(
        "codex", ["--global", "--no-hypothesis-hook"]
    )

    assert result == 1
    assert marker.read_text(encoding="utf-8") == "ambiguous custom lead\n"
    assert vendor.read_text(encoding="utf-8") == "vendor\n"
    canonical = home / ".agents" / "skills"
    assert (canonical / "lead").is_dir()
    assert os.path.samefile(
        legacy_skills / "backend-engineer", canonical / "backend-engineer"
    )
    assert not os.path.samefile(legacy_lead, canonical / "lead")


def test_exact_legacy_skill_authority_preserves_projects_and_replays(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    installer, home, legacy_skills = configured_home(tmp_path, monkeypatch)
    legacy_lead = legacy_skills / "lead"
    legacy_lead.mkdir(parents=True)
    marker = legacy_lead / "legacy.txt"
    marker.write_text("preserve exact legacy lead\n", encoding="utf-8")
    legacy_digest = installer._tree_sha256(
        legacy_lead, ignore_runtime_cache=True
    )
    assert legacy_digest is not None
    vendor = legacy_skills / "vendor-extension" / "marker.txt"
    vendor.parent.mkdir()
    vendor.write_text("vendor\n", encoding="utf-8")

    arguments = [
        "--global",
        "--no-hypothesis-hook",
        "--migrate-legacy-skill",
        "lead",
    ]
    before_dry_run = tree_bytes(home)
    assert installer.install("codex", [*arguments, "--dry-run"]) == 0
    dry_run_output = capsys.readouterr()
    assert "[dry-run] would preserve" in dry_run_output.out
    assert str(legacy_lead) in dry_run_output.out
    assert tree_bytes(home) == before_dry_run

    assert installer.install("codex", arguments) == 0
    output = capsys.readouterr()
    backup = (
        home
        / ".codex"
        / "orchestrarium-legacy-skills"
        / "lead"
        / legacy_digest
    )
    canonical_lead = home / ".agents" / "skills" / "lead"
    assert os.path.samefile(legacy_lead, canonical_lead)
    assert backup.joinpath("legacy.txt").read_text(encoding="utf-8") == (
        "preserve exact legacy lead\n"
    )
    assert str(backup) in output.out
    assert vendor.read_text(encoding="utf-8") == "vendor\n"

    before = tree_bytes(backup)
    assert installer.install("codex", arguments) == 0
    capsys.readouterr()
    assert os.path.samefile(legacy_lead, canonical_lead)
    assert tree_bytes(backup) == before


@pytest.mark.parametrize(
    ("provider", "arguments"),
    (
        ("codex", ("--global", "--migrate-legacy-skill", "../lead")),
        ("codex", ("--global", "--migrate-legacy-skill", "unknown-skill")),
        (
            "codex",
            (
                "--global",
                "--migrate-legacy-skill",
                "lead",
                "--migrate-legacy-skill",
                "lead",
            ),
        ),
        (
            "codex",
            (
                "--target",
                "project",
                "--allow-unsafe-target",
                "--migrate-legacy-skill",
                "lead",
            ),
        ),
        ("claude", ("--global", "--migrate-legacy-skill", "lead")),
    ),
)
def test_legacy_skill_authority_rejects_invalid_scope_before_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    arguments: tuple[str, ...],
) -> None:
    installer, home, _legacy_skills = configured_home(tmp_path, monkeypatch)
    before = tree_bytes(home)
    resolved_arguments = tuple(
        str(tmp_path / value) if value == "project" else value
        for value in arguments
    )

    result = installer.install(
        provider,
        [*resolved_arguments, "--no-hypothesis-hook"],
    )

    assert result == 1
    assert tree_bytes(home) == before


def test_repeated_distinct_legacy_skill_authority_is_admitted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installer, home, legacy_skills = configured_home(tmp_path, monkeypatch)

    result = installer.install(
        "codex",
        [
            "--global",
            "--no-hypothesis-hook",
            "--migrate-legacy-skill",
            "lead",
            "--migrate-legacy-skill",
            "analyst",
        ],
    )

    assert result == 0
    for name in ("lead", "analyst"):
        assert os.path.samefile(
            legacy_skills / name, home / ".agents" / "skills" / name
        )


@pytest.mark.parametrize("boundary", ("before-move", "before-link", "after-link"))
def test_legacy_skill_compatibility_failure_restores_exact_prestate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    installer, home, legacy_skills = configured_home(tmp_path, monkeypatch)
    legacy_lead = legacy_skills / "lead"
    legacy_lead.mkdir(parents=True)
    marker = legacy_lead / "legacy.txt"
    marker.write_text("restore exact legacy lead\n", encoding="utf-8")
    vendor = legacy_skills / "vendor-extension" / "marker.txt"
    vendor.parent.mkdir()
    vendor.write_text("vendor\n", encoding="utf-8")
    legacy_before = tree_bytes(legacy_skills)
    original_projection = installer._CreateOnlyMutablePath.create_projection
    original_replace = installer.os.replace

    def replace(source, target):
        if boundary == "before-move" and Path(source) == legacy_lead:
            raise OSError("injected before legacy move")
        return original_replace(source, target)

    def project(owner, relative, source):
        if boundary == "before-link" and relative.name == "lead":
            raise OSError("injected before legacy link")
        result = original_projection(owner, relative, source)
        if boundary == "after-link" and relative.name == "lead":
            raise OSError("injected after legacy link")
        return result

    monkeypatch.setattr(installer.os, "replace", replace)
    monkeypatch.setattr(
        installer._CreateOnlyMutablePath, "create_projection", project
    )

    result = installer.install(
        "codex",
        [
            "--global",
            "--no-hypothesis-hook",
            "--migrate-legacy-skill",
            "lead",
        ],
    )

    assert result == 1
    assert legacy_lead.is_dir() and not legacy_lead.is_symlink()
    assert tree_bytes(legacy_skills) == legacy_before
    assert vendor.read_text(encoding="utf-8") == "vendor\n"
    assert not (home / ".codex" / "orchestrarium-legacy-skills").exists()
    assert (home / ".agents" / "skills" / "lead").is_dir()
