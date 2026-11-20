"""Retired alias creation is inert; active copy-migration tests own conversion."""
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
    "--model", "gpt-6.1-sol", "-c", "model_reasoning_effort=high",
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


def test_codex_install_preserves_legacy_root_without_creating_aliases(
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
    assert not os.path.lexists(legacy_lead)
    assert os.path.samefile(legacy_skills, legacy_store)
    assert installer._CreateOnlyMutablePath._identity(legacy_skills) == root_identity
    canonical_names = sorted(
        path.name for path in canonical_lead.parent.iterdir() if path.is_dir()
    )
    assert canonical_names
    for name in canonical_names:
        assert not os.path.lexists(legacy_skills / name)
    assert vendor_marker.read_text(encoding="utf-8") == "preserve vendor skill\n"

    for label, lead in (("canonical", canonical_lead),):
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
        assert "gpt-6.1-sol" in probed.stdout
        assert "INVALID: invalid launch flags" in probed.stdout
        assert "Traceback" not in probed.stdout + probed.stderr




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


def test_unselected_legacy_custom_skill_does_not_block_independent_install(
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

    assert result == 0
    assert marker.read_text(encoding="utf-8") == "ambiguous custom lead\n"
    assert vendor.read_text(encoding="utf-8") == "vendor\n"
    canonical = home / ".agents" / "skills"
    assert (canonical / "lead").is_dir()
    assert not os.path.lexists(legacy_skills / "backend-engineer")
    assert not os.path.samefile(legacy_lead, canonical / "lead")



@pytest.mark.parametrize("provider", ("codex", "claude"))
@pytest.mark.parametrize("scope", ("global", "target"))
@pytest.mark.parametrize("dry_run", (False, True))
def test_retired_alias_creation_flag_refuses_before_mutation(
    tmp_path, monkeypatch, capsys, provider, scope, dry_run
):
    installer, home, legacy = configured_home(tmp_path, monkeypatch)
    marker = legacy / "lead/user.txt"
    marker.parent.mkdir(parents=True)
    marker.write_bytes(b"unmanaged old skill")
    target = tmp_path / "project"
    target.mkdir()
    (target / "user.txt").write_bytes(b"preserve project")
    before_home = installer._InstallTransaction._observe(home)
    before_target = installer._InstallTransaction._observe(target)
    args = ["--global"] if scope == "global" else ["--target", str(target)]
    args += ["--migrate-legacy-skill", "lead", "--migrate-legacy-skill", "analyst"]
    if dry_run:
        args.append("--dry-run")
    assert installer.install(provider, args) == 1
    assert installer._InstallTransaction._observe(home) == before_home
    assert installer._InstallTransaction._observe(target) == before_target
    error = capsys.readouterr().err
    assert "E_LEGACY_CODEX_SKILL_ARGUMENT" in error
    assert "retired" in error
    assert "--materialize-legacy-skills" in error
