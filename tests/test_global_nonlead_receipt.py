from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "production_installer.py"
RECEIPT = ".orchestrarium-nonlead-skills-receipt.v1.json"
SCHEMA = "orchestrarium.canonical-nonlead-skills-install.v1"
NAMES = ("analyst", "knowledge-archivist")


def _installer():
    spec = importlib.util.spec_from_file_location("nonlead_receipt_installer", INSTALLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fixture(tmp_path: Path):
    installer = _installer()
    source = tmp_path / "source"
    source.mkdir()
    shutil.copytree(ROOT / "src.codex" / "skills" / "lead", source / "lead")
    for name in NAMES:
        skill = source / name
        skill.mkdir()
        (skill / "SKILL.md").write_bytes(f"{name} version A\n".encode())
    home = tmp_path / "home"
    skills = home / ".agents" / "skills"
    skills.mkdir(parents=True)
    return installer, source, home, skills, skills / RECEIPT


def _apply(installer, source: Path, home: Path, skills: Path) -> None:
    plan = installer._preflight_canonical_skills(
        source, skills, root=ROOT, global_install=True
    )
    try:
        with installer._InstallTransaction([skills], enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
            installer._apply_canonical_skills_plan(plan, skills, owner, root=ROOT)
            transaction.commit()
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_nonlead_receipt_two_named_skills_upgrade_a_b_c(tmp_path: Path) -> None:
    """A version change for either name must update one shared receipt map."""
    installer, source, home, skills, receipt = _fixture(tmp_path)
    versions: list[dict[str, str]] = []
    for version in "ABC":
        for name in NAMES:
            (source / name / "SKILL.md").write_bytes(
                f"{name} version {version}\n".encode()
            )
        _apply(installer, source, home, skills)
        observed = {
            name: installer._tree_sha256(skills / name, ignore_runtime_cache=True)
            for name in NAMES
        }
        assert json.loads(receipt.read_bytes()) == {
            "schema": SCHEMA, "skills": observed,
        }
        versions.append(observed)
    assert all(versions[0][name] != versions[1][name] != versions[2][name]
               for name in NAMES)


def _inventory(root: Path) -> dict[str, tuple[str, bytes | str]]:
    result: dict[str, tuple[str, bytes | str]] = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = ("link", str(path.readlink()))
        elif path.is_file():
            result[relative] = ("file", path.read_bytes())
        elif path.is_dir():
            result[relative] = ("directory", "")
    return result


def test_nonlead_unreceipted_unknown_requires_exact_grant(tmp_path: Path) -> None:
    installer, source, home, skills, receipt = _fixture(tmp_path)
    _apply(installer, source, home, skills)
    receipt.unlink()
    (source / "knowledge-archivist" / "SKILL.md").write_bytes(b"next release\n")
    observed = installer._tree_sha256(skills / "knowledge-archivist", ignore_runtime_cache=True)
    with pytest.raises(ValueError, match=f"E_CANONICAL_SKILL_ADOPTION_REQUIRED: knowledge-archivist={observed}"):
        installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
    for grants in (
        ("knowledge-archivist=" + "0" * 64,),
        ("knowledge-archivist=" + observed.upper(),),
        ("knowledge-archivist=" + observed,) * 2,
        ("lead=" + observed,),
        ("other-skill=" + observed,),
    ):
        with pytest.raises(ValueError, match="E_CANONICAL_SKILL_ADOPTION_MISMATCH"):
            installer._preflight_canonical_skills(
                source, skills, root=ROOT, global_install=True,
                replace_unreceipted_skill_sha256=grants,
            )
    plan = installer._preflight_canonical_skills(
        source, skills, root=ROOT, global_install=True,
        replace_unreceipted_skill_sha256=(f"knowledge-archivist={observed}",),
    )
    try:
        with installer._InstallTransaction([skills], enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
            installer._apply_canonical_skills_plan(plan, skills, owner, root=ROOT)
            transaction.commit()
    finally:
        installer._discard_canonical_skills_plan(plan)
    assert json.loads(receipt.read_bytes())["skills"]["knowledge-archivist"] == installer._tree_sha256(
        skills / "knowledge-archivist", ignore_runtime_cache=True
    )
    with pytest.raises(ValueError, match="E_CANONICAL_SKILL_ADOPTION_MISMATCH"):
        installer._preflight_canonical_skills(
            source, skills, root=ROOT, global_install=True,
            replace_unreceipted_skill_sha256=(f"knowledge-archivist={observed}",),
        )


@pytest.mark.parametrize("drift", ["byte", "extra", "missing", "map-member"])
def test_nonlead_receipted_drift_refuses_without_writes(tmp_path: Path, drift: str) -> None:
    installer, source, home, skills, receipt = _fixture(tmp_path)
    _apply(installer, source, home, skills)
    if drift == "byte":
        (skills / "analyst" / "SKILL.md").write_bytes(b"customized")
    elif drift == "extra":
        (skills / "analyst" / "extra.txt").write_bytes(b"customized")
    elif drift == "missing":
        shutil.rmtree(skills / "analyst")
    else:
        entries = json.loads(receipt.read_bytes())
        del entries["skills"]["analyst"]
        receipt.write_bytes((json.dumps(entries, separators=(",", ":")) + "\n").encode())
    (source / "analyst" / "SKILL.md").write_bytes(b"new source")
    before = _inventory(skills)
    signal = "E_CANONICAL_SKILLS_RECEIPT_INVALID" if drift == "map-member" else "E_CANONICAL_SKILLS_RECEIPT_DRIFT: analyst"
    with pytest.raises(ValueError, match=signal):
        installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
    assert _inventory(skills) == before


def test_nonlead_current_stale_map_repairs_only_receipt(tmp_path: Path) -> None:
    installer, source, home, skills, receipt = _fixture(tmp_path)
    _apply(installer, source, home, skills)
    original = receipt.read_bytes()
    inodes = {name: (skills / name).stat().st_ino for name in NAMES}
    record = json.loads(original)
    record["skills"]["analyst"] = "0" * 64
    receipt.write_bytes((json.dumps(record, separators=(",", ":")) + "\n").encode())
    _apply(installer, source, home, skills)
    assert receipt.read_bytes() == original
    assert {name: (skills / name).stat().st_ino for name in NAMES} == inodes


@pytest.mark.parametrize("invalid", [
    b"{",
    b"{}\n",
    b'{"schema":"wrong","skills":{}}\n',
    b'{"schema":"orchestrarium.canonical-nonlead-skills-install.v1","skills":{"lead":"' + b"0" * 64 + b'"}}\n',
    b'{"schema":"orchestrarium.canonical-nonlead-skills-install.v1","skills":{"../escape":"' + b"0" * 64 + b'"}}\n',
    b'{"schema":"orchestrarium.canonical-nonlead-skills-install.v1","skills":{"analyst":"' + b"A" * 64 + b'"}}\n',
    b'{"schema":"orchestrarium.canonical-nonlead-skills-install.v1","skills":{},"extra":1}\n',
    b'{"schema":"orchestrarium.canonical-nonlead-skills-install.v1","skills":{"analyst":"' + b"0" * 64 + b'","analyst":"' + b"0" * 64 + b'"}}\n',
    b'{"schema":"orchestrarium.canonical-nonlead-skills-install.v1","skills":{"knowledge-archivist":"' + b"0" * 64 + b'","analyst":"' + b"0" * 64 + b'"}}\n',
    b'{ "schema":"orchestrarium.canonical-nonlead-skills-install.v1","skills":{}}\n',
])
def test_nonlead_invalid_map_refuses(tmp_path: Path, invalid: bytes) -> None:
    installer, source, home, skills, receipt = _fixture(tmp_path)
    _apply(installer, source, home, skills)
    receipt.write_bytes(invalid)
    with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_INVALID"):
        installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)


@pytest.mark.parametrize("failpoint", ["tree", "map"])
def test_nonlead_tree_and_map_transaction_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failpoint: str
) -> None:
    installer, source, home, skills, receipt = _fixture(tmp_path)
    _apply(installer, source, home, skills)
    before = _inventory(skills)
    (source / "analyst" / "SKILL.md").write_bytes(b"next source")
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
    try:
        method = (installer._CreateOnlyMutablePath.replace_exact_tree if failpoint == "tree"
                  else installer._CreateOnlyMutablePath.replace_exact_file)
        def abort_after(self, *args, **kwargs):
            result = method(self, *args, **kwargs)
            raise RuntimeError("after nonlead " + failpoint)
        monkeypatch.setattr(installer._CreateOnlyMutablePath, method.__name__, abort_after)
        with pytest.raises(RuntimeError, match="after nonlead"):
            with installer._InstallTransaction([skills], enabled=True) as transaction:
                owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
                installer._apply_canonical_skills_plan(plan, skills, owner, root=ROOT)
                transaction.commit()
    finally:
        installer._discard_canonical_skills_plan(plan)
    assert _inventory(skills) == before


def test_nonlead_global_cli_adoption_dry_run_reports_exact_grant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installer = _installer()
    home = tmp_path / "home"
    skills = home / ".agents" / "skills"
    skills.mkdir(parents=True)
    _apply(installer, ROOT / "src.codex" / "skills", home, skills)
    (skills / RECEIPT).unlink()
    with (skills / "knowledge-archivist" / "SKILL.md").open("ab") as stream:
        stream.write(b"unreceipted legacy bytes")
    observed = installer._tree_sha256(skills / "knowledge-archivist", ignore_runtime_cache=True)
    before = _inventory(home)
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    assert installer.install("codex", ["--global", "--force", "--dry-run",
                                        "--no-hypothesis-hook"]) == 1
    assert f"knowledge-archivist={observed}" in capsys.readouterr().err
    assert installer.install("codex", [
        "--global", "--dry-run", "--no-hypothesis-hook",
        "--replace-unreceipted-skill-sha256", f"knowledge-archivist={observed}",
    ]) == 0
    output = capsys.readouterr().out
    assert f"knowledge-archivist={observed}" in output
    assert "2 replacements" in output
    assert _inventory(home) == before


def test_nonlead_map_identity_drift_rejected_before_writer(tmp_path: Path) -> None:
    installer, source, home, skills, receipt = _fixture(tmp_path)
    _apply(installer, source, home, skills)
    (source / "analyst" / "SKILL.md").write_bytes(b"next version")
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
    try:
        replacement = skills / "replacement.json"
        replacement.write_bytes(receipt.read_bytes())
        os.replace(replacement, receipt)
        before = _inventory(skills)
        owner = installer._CreateOnlyMutablePath(
            home, installer._InstallTransaction([], enabled=False), dry_run=False
        )
        with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_DRIFT"):
            installer._apply_canonical_skills_plan(plan, skills, owner, root=ROOT)
        assert _inventory(skills) == before
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_nonlead_source_membership_drift_rejected_before_writer(tmp_path: Path) -> None:
    installer, source, home, skills, _receipt = _fixture(tmp_path)
    _apply(installer, source, home, skills)
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
    try:
        (source / "new-skill").mkdir()
        (source / "new-skill" / "SKILL.md").write_bytes(b"new")
        before = _inventory(skills)
        owner = installer._CreateOnlyMutablePath(
            home, installer._InstallTransaction([], enabled=False), dry_run=False
        )
        with pytest.raises(ValueError, match="preflight drift"):
            installer._apply_canonical_skills_plan(plan, skills, owner, root=ROOT)
        assert _inventory(skills) == before
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_nonlead_linked_map_and_removed_source_refuse(tmp_path: Path) -> None:
    installer, source, home, skills, receipt = _fixture(tmp_path)
    _apply(installer, source, home, skills)
    payload = receipt.read_bytes()
    receipt.unlink()
    foreign = tmp_path / "foreign.json"
    foreign.write_bytes(payload)
    try:
        receipt.symlink_to(foreign)
    except OSError:
        pytest.skip("file symlinks unavailable")
    with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_INVALID"):
        installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
    receipt.unlink()
    receipt.write_bytes(payload)
    shutil.rmtree(source / "analyst")
    with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_INVALID"):
        installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)


def test_nonlead_project_mode_keeps_prior_admission_and_no_map(tmp_path: Path) -> None:
    installer, source, home, skills, receipt = _fixture(tmp_path)
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT)
    try:
        with installer._InstallTransaction([skills], enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
            installer._apply_canonical_skills_plan(plan, skills, owner, root=ROOT)
            transaction.commit()
    finally:
        installer._discard_canonical_skills_plan(plan)
    assert not receipt.exists()
    (source / "analyst" / "SKILL.md").write_bytes(b"next version")
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: analyst"):
        installer._preflight_canonical_skills(source, skills, root=ROOT)
    with pytest.raises(ValueError, match="E_CANONICAL_SKILL_ADOPTION_MISMATCH"):
        installer._preflight_canonical_skills(
            source, skills, root=ROOT,
            replace_unreceipted_skill_sha256=("analyst=" + "0" * 64,),
        )


def test_nonlead_old_curated_prior_seeds_map(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    installer, source, home, skills, receipt = _fixture(tmp_path)
    _apply(installer, source, home, skills)
    receipt.unlink()
    prior = installer._tree_sha256(skills / "analyst", ignore_runtime_cache=True)
    monkeypatch.setitem(installer.E7_CANONICAL_SKILL_TREE_SHA256, "analyst", prior)
    (source / "analyst" / "SKILL.md").write_bytes(b"new version")
    _apply(installer, source, home, skills)
    assert json.loads(receipt.read_bytes())["skills"]["analyst"] == installer._tree_sha256(
        skills / "analyst", ignore_runtime_cache=True
    )


@pytest.mark.parametrize("order", [("codex", "claude"), ("claude", "codex")])
def test_nonlead_provider_orders_without_git_preserve_links_and_lead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, order: tuple[str, str]
) -> None:
    installer = _installer()
    receiver = tmp_path / "receiver"
    receiver.mkdir()
    archive = subprocess.run(["git", "archive", "--format=tar", "HEAD"],
                             cwd=ROOT, check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as package:
        package.extractall(receiver, filter="data")
    assert not (receiver / ".git").exists()
    monkeypatch.setattr(installer, "_repo_root", lambda _script: receiver)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    assert installer.install(order[0], ["--global", "--no-hypothesis-hook"]) == 0
    skills = home / ".agents" / "skills"
    lead_receipt = skills / ".orchestrarium-lead-receipt.v1.json"
    lead_bytes = lead_receipt.read_bytes()
    receipt = skills / RECEIPT
    prior = json.loads(receipt.read_bytes())["skills"]
    links = {provider: (home / f".{provider}" / "skills" / "lead").lstat().st_ino
             for provider in ("codex", "claude")
             if (home / f".{provider}" / "skills" / "lead").exists()}
    for name in NAMES:
        with (receiver / "src.codex" / "skills" / name / "SKILL.md").open("ab") as stream:
            stream.write(b"\nsynthetic second version\n")
    assert installer.install(order[1], ["--global", "--no-hypothesis-hook"]) == 0
    current = json.loads(receipt.read_bytes())["skills"]
    for name in NAMES:
        assert current[name] != prior[name]
        assert current[name] == installer._tree_sha256(skills / name, ignore_runtime_cache=True)
    assert lead_receipt.read_bytes() == lead_bytes
    for provider, inode in links.items():
        assert (home / f".{provider}" / "skills" / "lead").lstat().st_ino == inode


def test_nonlead_claude_projection_failure_rolls_back_map_and_trees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = _installer()
    receiver = tmp_path / "receiver"
    receiver.mkdir()
    archive = subprocess.run(["git", "archive", "--format=tar", "HEAD"],
                             cwd=ROOT, check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as package:
        package.extractall(receiver, filter="data")
    monkeypatch.setattr(installer, "_repo_root", lambda _script: receiver)
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    assert installer.install("codex", ["--global", "--no-hypothesis-hook"]) == 0
    before = _inventory(home)
    with (receiver / "src.codex" / "skills" / "analyst" / "SKILL.md").open("ab") as stream:
        stream.write(b"\nchanged source\n")
    original = installer._apply_claude_skill_projection_plan
    def fail_after_projection(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected after Claude projection")
    monkeypatch.setattr(installer, "_apply_claude_skill_projection_plan", fail_after_projection)
    assert installer.install("claude", ["--global", "--no-hypothesis-hook"]) == 1
    assert _inventory(home) == before


def test_nonlead_mixed_case_safe_names_install_then_upgrade(tmp_path: Path) -> None:
    installer, source, home, skills, receipt = _fixture(tmp_path)
    for name in NAMES:
        shutil.rmtree(source / name)
    for name in ("a", "Z"):
        skill = source / name
        skill.mkdir()
        (skill / "SKILL.md").write_bytes(f"{name} version A\n".encode())
    _apply(installer, source, home, skills)
    first = json.loads(receipt.read_bytes())
    assert set(first["skills"]) == {"a", "Z"}
    for name in ("a", "Z"):
        (source / name / "SKILL.md").write_bytes(f"{name} version B\n".encode())
    _apply(installer, source, home, skills)
    second = json.loads(receipt.read_bytes())
    for name in ("a", "Z"):
        assert second["skills"][name] != first["skills"][name]
        assert second["skills"][name] == installer._tree_sha256(
            skills / name, ignore_runtime_cache=True
        )
