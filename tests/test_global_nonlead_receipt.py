from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from _filesystem_fixture_support import (
    _flip_directory_binding_attributes,
    _write_directory_attributes,
)


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


def test_nonlead_tree_commit_accepts_directory_metadata_binding_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if os.name != "nt":
        pytest.skip("Windows directory attribute binding")
    installer, source, home, skills, receipt = _fixture(tmp_path)
    monkeypatch.setattr(installer.tempfile, "tempdir", str(tmp_path))
    _apply(installer, source, home, skills)
    sibling = skills / "operator-data.bin"
    sibling.write_bytes(b"protected sibling")
    lead_before = _inventory(skills / "lead")
    receipt_before = receipt.read_bytes()
    (source / "analyst" / "SKILL.md").write_bytes(b"next source\n")
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
    analyst = skills / "analyst"
    changed = []
    original_replace = installer._CreateOnlyMutablePath.replace_exact_tree

    def publish_then_drift(owner, relative, *args, **kwargs):
        result = original_replace(owner, relative, *args, **kwargs)
        if owner.anchor / relative == analyst:
            changed.append(_flip_directory_binding_attributes(installer, analyst))
        return result

    monkeypatch.setattr(installer._CreateOnlyMutablePath, "replace_exact_tree", publish_then_drift)
    try:
        with installer._InstallTransaction([skills], enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
            installer._apply_canonical_skills_plan(plan, skills, owner, root=ROOT)
            transaction.commit()
        assert changed
        assert (analyst / "SKILL.md").read_bytes() == b"next source\n"
        assert receipt.read_bytes() != receipt_before
        receipt_data = json.loads(receipt.read_bytes())
        assert receipt_data == {
            "schema": SCHEMA,
            "skills": {
                name: installer._tree_sha256(skills / name, ignore_runtime_cache=True)
                for name in NAMES
            },
        }
        assert _inventory(skills / "lead") == lead_before
        assert sibling.read_bytes() == b"protected sibling"
        assert transaction._temporary is None
    finally:
        installer._discard_canonical_skills_plan(plan)
        if analyst.exists():
            analyst.chmod(stat.S_IMODE(analyst.stat().st_mode) | stat.S_IWRITE)
    assert not tuple(tmp_path.glob("orchestrarium-install-transaction-*"))


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


def _member_fixture(tmp_path: Path):
    installer, source, home, skills, receipt = _fixture(tmp_path)
    (source / "analyst" / "agents").mkdir()
    (source / "analyst" / "agents" / "openai.yaml").write_bytes(b"genuine old metadata\n")
    _apply(installer, source, home, skills)
    entries = json.loads(receipt.read_bytes())["skills"]
    entries["analyst"] = {"members": dict(installer._stage_tree_manifest(skills / "analyst"))}
    receipt.write_bytes(installer._nonlead_receipt_bytes(entries))
    (skills / "analyst" / "operator-note.bin").write_bytes(b"protected operator bytes")
    (source / "analyst" / "SKILL.md").write_bytes(b"selected new body\n")
    (source / "analyst" / "agents" / "openai.yaml").write_bytes(b"unselected new metadata\n")
    return installer, source, home, skills, receipt


def _apply_member_plan(installer, plan, home: Path, skills: Path) -> None:
    with installer._InstallTransaction([skills], enabled=True) as transaction:
        owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
        installer._apply_canonical_skills_plan(plan, skills, owner, root=ROOT)
        transaction.commit()


def test_member_receipt_mixed_wire_and_explicit_v2_roundtrip(tmp_path: Path) -> None:
    installer = _installer()
    entries = {"analyst": {"members": {"SKILL.md": "1" * 64}}, "knowledge-archivist": "2" * 64}
    receipt = tmp_path / RECEIPT
    payload = installer._nonlead_receipt_bytes(entries)
    receipt.write_bytes(payload)
    observed = installer._read_nonlead_receipt(receipt)
    assert observed.schema == "orchestrarium.canonical-nonlead-skills-install.v2"
    assert observed.entries == (("analyst", (("SKILL.md", "1" * 64),)), ("knowledge-archivist", "2" * 64))
    assert observed.payload == payload
    legacy = {"analyst": "1" * 64}
    receipt.write_bytes(installer._nonlead_receipt_bytes(legacy, schema=observed.schema))
    assert installer._read_nonlead_receipt(receipt).schema == observed.schema


@pytest.mark.parametrize("members", [
    {}, {"../escape": "1" * 64}, {"/absolute": "1" * 64}, {"C:/drive": "1" * 64},
    {"agents\\meta": "1" * 64}, {"./SKILL.md": "1" * 64}, {"SKILL.md": "A" * 64},
    {"SKILL.md": "1" * 64, "skill.md": "1" * 64},
    {"agents": "1" * 64, "agents/meta": "1" * 64}, {"agents/meta": "1" * 64},
    {"agents ": "directory"},
])
def test_member_receipt_invalid_paths_and_parent_relations(tmp_path: Path, members) -> None:
    installer = _installer()
    record = {"schema": "orchestrarium.canonical-nonlead-skills-install.v2",
              "skills": {"analyst": {"members": members}}}
    receipt = tmp_path / RECEIPT
    receipt.write_bytes((json.dumps(record, separators=(",", ":")) + "\n").encode())
    with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_INVALID"):
        installer._read_nonlead_receipt(receipt)


def test_member_receipt_duplicate_nested_keys_and_v1_object_refuse(tmp_path: Path) -> None:
    installer = _installer()
    receipt = tmp_path / RECEIPT
    receipt.write_bytes(b'{"schema":"orchestrarium.canonical-nonlead-skills-install.v2","skills":{"analyst":{"members":{"SKILL.md":"'
                        + b"1" * 64 + b'","SKILL.md":"' + b"1" * 64 + b'"}}}}\n')
    with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_INVALID"):
        installer._read_nonlead_receipt(receipt)
    receipt.write_bytes(installer._nonlead_receipt_bytes({"analyst": {"members": {"SKILL.md": "1" * 64}}}, schema=SCHEMA))
    with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_INVALID"):
        installer._read_nonlead_receipt(receipt)


def test_member_selected_body_preserves_old_yaml_extras_and_other_entries(tmp_path: Path) -> None:
    installer, source, home, skills, receipt = _member_fixture(tmp_path)
    before_entries = json.loads(receipt.read_bytes())["skills"]
    protected = [skills / "analyst", skills / "analyst" / "agents",
                 skills / "analyst" / "agents" / "openai.yaml", skills / "analyst" / "operator-note.bin"]
    witnesses = {path: installer._InstallTransaction._capture_node(path) for path in protected}
    (source / "knowledge-archivist" / "SKILL.md").write_bytes(b"unselected other skill")
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                                member_selection=(("analyst", ("SKILL.md",)),))
    try:
        selected = plan.skills[0]
        assert selected.managed_after != installer._stage_tree_manifest(source / "analyst")
        (source / "analyst" / "agents" / "openai.yaml").write_bytes(b"later unselected Source metadata\n")
        _apply_member_plan(installer, plan, home, skills)
        assert (skills / "analyst" / "SKILL.md").read_bytes() == b"selected new body\n"
        assert all(installer._InstallTransaction._point_matches(path, node, check_file_content=True)
                   for path, node in witnesses.items())
        current = json.loads(receipt.read_bytes())["skills"]
        assert current["analyst"] == {"members": dict(selected.managed_after)}
        assert current["knowledge-archivist"] == before_entries["knowledge-archivist"]
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_member_full_selection_updates_yaml_but_preserves_extra(tmp_path: Path) -> None:
    installer, source, home, skills, _receipt = _member_fixture(tmp_path)
    extra = installer._InstallTransaction._capture_node(skills / "analyst" / "operator-note.bin")
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True)
    try:
        member = next(skill for skill in plan.skills if skill.name == "analyst")
        assert member.managed_after == installer._stage_tree_manifest(source / "analyst")
        _apply_member_plan(installer, plan, home, skills)
        assert (skills / "analyst" / "agents" / "openai.yaml").read_bytes() == b"unselected new metadata\n"
        assert installer._InstallTransaction._point_matches(skills / "analyst" / "operator-note.bin", extra, check_file_content=True)
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_member_matching_v1_explicit_empty_selection_changes_only_receipt(tmp_path: Path) -> None:
    installer, source, home, skills, receipt = _fixture(tmp_path)
    _apply(installer, source, home, skills)
    before = _inventory(skills)
    nodes = installer._InstallTransaction._observe(skills / "analyst")
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                                member_selection=(("analyst", ()),))
    try:
        assert plan.skills[0].selection == ()
        assert plan.skills[0].managed_before == plan.skills[0].managed_after
        _apply_member_plan(installer, plan, home, skills)
        after = _inventory(skills)
        assert {path: value for path, value in before.items() if path != RECEIPT} == {
            path: value for path, value in after.items() if path != RECEIPT}
        assert installer._InstallTransaction._image_matches(skills / "analyst", nodes)
        assert isinstance(json.loads(receipt.read_bytes())["skills"]["analyst"], dict)
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_member_drifting_v1_cannot_be_reconstructed_from_current_source(tmp_path: Path) -> None:
    installer, source, home, skills, _receipt = _fixture(tmp_path)
    _apply(installer, source, home, skills)
    (skills / "analyst" / "SKILL.md").write_bytes(b"same new bytes")
    (source / "analyst" / "SKILL.md").write_bytes(b"same new bytes")
    before = _inventory(skills)
    with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_DRIFT"):
        installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                             member_selection=(("analyst", ()),))
    assert _inventory(skills) == before


@pytest.mark.parametrize("selected", ["operator-note.bin", "operator-note.bin/child"])
def test_member_selected_addition_cannot_adopt_protected_collision(tmp_path: Path, selected: str) -> None:
    installer, source, _home, skills, _receipt = _member_fixture(tmp_path)
    candidate = source / "analyst" / selected
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_bytes(b"protected operator bytes")
    before = _inventory(skills)
    with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: protected member"):
        installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                             member_selection=(("analyst", (selected,)),))
    assert _inventory(skills) == before


@pytest.mark.parametrize("drift", ["selected-identity", "protected", "source-selected", "receipt-identity"])
def test_member_preflight_drift_refuses_before_effects(tmp_path: Path, drift: str) -> None:
    installer, source, home, skills, receipt = _member_fixture(tmp_path)
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                                member_selection=(("analyst", ("SKILL.md",)),))
    try:
        if drift in {"selected-identity", "receipt-identity"}:
            path = skills / "analyst" / "SKILL.md" if drift == "selected-identity" else receipt
            replacement = home / "replacement"
            replacement.write_bytes(path.read_bytes())
            os.replace(replacement, path)
        elif drift == "protected":
            (skills / "analyst" / "operator-note.bin").write_bytes(b"foreign change")
        else:
            (source / "analyst" / "SKILL.md").write_bytes(b"late source change")
        before = _inventory(skills)
        with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_DRIFT"):
            _apply_member_plan(installer, plan, home, skills)
        assert _inventory(skills) == before
    finally:
        installer._discard_canonical_skills_plan(plan)


@pytest.mark.parametrize("failure", ["member", "receipt", "cancel"])
def test_member_and_receipt_failure_restore_native_preimages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    installer, source, home, skills, _receipt = _member_fixture(tmp_path)
    before = _inventory(skills)
    physical = installer._InstallTransaction._observe(skills / "analyst")
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                                member_selection=(("analyst", ("SKILL.md",)),))
    method_name = "replace_exact_file" if failure == "receipt" else "migrate_exact_file"
    original = getattr(installer._CreateOnlyMutablePath, method_name)
    error = KeyboardInterrupt if failure == "cancel" else RuntimeError
    def fail_after(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise error("injected member receipt failure")
    monkeypatch.setattr(installer._CreateOnlyMutablePath, method_name, fail_after)
    try:
        with pytest.raises(error, match="injected member receipt failure"):
            _apply_member_plan(installer, plan, home, skills)
        assert _inventory(skills) == before
        assert installer._InstallTransaction._image_matches(skills / "analyst", physical)
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_member_both_projection_consumers_receive_same_selected_after_map(tmp_path: Path) -> None:
    installer, source, home, skills, _receipt = _member_fixture(tmp_path)
    codex = home / ".codex" / "skills"
    claude = home / ".claude" / "skills"
    codex.mkdir(parents=True)
    claude.mkdir(parents=True)
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                                member_selection=(("analyst", ("SKILL.md",)),))
    try:
        codex_plan, identity = installer._preflight_codex_legacy_skill_projections(
            plan, skills, codex, home / "backups", frozenset())
        claude_plan = installer._preflight_claude_skill_projections(
            source, tmp_path / "historical", skills, claude, canonical_plan=plan)
        assert claude_plan[0].canonical_skill is plan.skills[0]
        _apply_member_plan(installer, plan, home, skills)
        installer._assert_codex_legacy_skill_projection_plan_current(codex_plan, plan, codex, identity, dry_run=False)
        installer._assert_claude_skill_projection_plan_current(claude_plan, source, claude)
        (skills / "analyst" / "operator-note.bin").write_bytes(b"foreign postcondition drift")
        with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_DRIFT"):
            installer._assert_codex_legacy_skill_projection_plan_current(codex_plan, plan, codex, identity, dry_run=False)
        with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_DRIFT"):
            installer._assert_claude_skill_projection_plan_current(claude_plan, source, claude)
    finally:
        installer._discard_canonical_skills_plan(plan)


@pytest.mark.parametrize("source_parent", ["absent", "file"])
def test_member_partial_removal_preserves_unselected_sibling_and_required_parent(
    tmp_path: Path, source_parent: str
) -> None:
    installer, source, home, skills, receipt = _member_fixture(tmp_path)
    sibling = skills / "analyst" / "agents" / "retained.yaml"
    sibling.write_bytes(b"unselected managed sibling\n")
    entries = json.loads(receipt.read_bytes())["skills"]
    entries["analyst"]["members"]["agents/retained.yaml"] = hashlib.sha256(sibling.read_bytes()).hexdigest()
    receipt.write_bytes(installer._nonlead_receipt_bytes(entries))
    protected = [skills / "analyst", sibling.parent, sibling, skills / "analyst" / "operator-note.bin"]
    witnesses = {path: installer._InstallTransaction._capture_node(path) for path in protected}
    before = _inventory(skills)
    (source / "analyst" / "agents" / "openai.yaml").unlink()
    (source / "analyst" / "agents").rmdir()
    if source_parent == "file":
        (source / "analyst" / "agents").write_bytes(b"unselected Source parent file\n")
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                                member_selection=(("analyst", ("agents/openai.yaml",)),))
    try:
        member = plan.skills[0]
        expected_members = dict(entries["analyst"]["members"])
        del expected_members["agents/openai.yaml"]
        assert member.selection == (("agents/openai.yaml", None),)
        assert dict(member.managed_after) == expected_members
        _apply_member_plan(installer, plan, home, skills)
        assert not (skills / "analyst" / "agents" / "openai.yaml").exists()
        assert all(installer._InstallTransaction._point_matches(path, node, check_file_content=True)
                   for path, node in witnesses.items())
        assert _inventory(skills) == {path: value for path, value in before.items()
                                     if path not in {RECEIPT, "analyst/agents/openai.yaml"}} | {
                                         RECEIPT: ("file", receipt.read_bytes())}
        entries["analyst"] = {"members": expected_members}
        assert json.loads(receipt.read_bytes())["skills"] == entries
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_member_last_child_removal_retains_unselected_directory(tmp_path: Path) -> None:
    installer, source, home, skills, receipt = _member_fixture(tmp_path)
    entries = json.loads(receipt.read_bytes())["skills"]
    nodes = installer._InstallTransaction._observe(skills / "analyst")
    (source / "analyst" / "agents" / "openai.yaml").unlink()
    (source / "analyst" / "agents").rmdir()
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                                member_selection=(("analyst", ("agents/openai.yaml",)),))
    try:
        member = plan.skills[0]
        expected = dict(entries["analyst"]["members"])
        del expected["agents/openai.yaml"]
        assert member.selection == (("agents/openai.yaml", None),)
        assert dict(member.managed_after) == expected
        _apply_member_plan(installer, plan, home, skills)
        assert not (skills / "analyst" / "agents" / "openai.yaml").exists()
        assert all(installer._InstallTransaction._point_matches(path, node, check_file_content=True)
                   for path, node in nodes.items() if path != skills / "analyst" / "agents" / "openai.yaml")
        entries["analyst"] = {"members": expected}
        assert json.loads(receipt.read_bytes())["skills"] == entries
    finally:
        installer._discard_canonical_skills_plan(plan)


@pytest.mark.parametrize("conflict", ["explicit-parent-removal", "existing-file-parent"])
def test_member_directory_closure_refuses_parent_conflicts(tmp_path: Path, conflict: str) -> None:
    installer, source, _home, skills, receipt = _member_fixture(tmp_path)
    if conflict == "explicit-parent-removal":
        (source / "analyst" / "agents" / "openai.yaml").unlink()
        (source / "analyst" / "agents").rmdir()
        selected = "agents"
    else:
        (skills / "analyst" / "assets").write_bytes(b"authenticated managed file\n")
        entries = json.loads(receipt.read_bytes())["skills"]
        entries["analyst"]["members"]["assets"] = hashlib.sha256(
            (skills / "analyst" / "assets").read_bytes()).hexdigest()
        receipt.write_bytes(installer._nonlead_receipt_bytes(entries))
        (source / "analyst" / "assets").mkdir()
        (source / "analyst" / "assets" / "child").write_bytes(b"selected child\n")
        selected = "assets/child"
    before = _inventory(skills)
    nodes = installer._InstallTransaction._observe(skills / "analyst")
    with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_INVALID: member parent"):
        installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                             member_selection=(("analyst", (selected,)),))
    assert _inventory(skills) == before
    assert installer._InstallTransaction._image_matches(skills / "analyst", nodes)


def test_member_directory_closure_and_owned_file_removal_preserve_container_identity(tmp_path: Path) -> None:
    installer, source, home, skills, receipt = _member_fixture(tmp_path)
    container = installer._InstallTransaction._capture_node(skills / "analyst" / "agents")
    (source / "analyst" / "agents" / "openai.yaml").unlink()
    (source / "analyst" / "agents").rmdir()
    (source / "analyst" / "assets").mkdir()
    (source / "analyst" / "assets" / "body.txt").write_bytes(b"selected new child")
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                                member_selection=(("analyst", ("agents", "agents/openai.yaml", "assets/body.txt")),))
    try:
        member = plan.skills[0]
        assert member.selection == (("agents", None), ("agents/openai.yaml", None),
                                    ("assets", "directory"),
                                    ("assets/body.txt", hashlib.sha256(b"selected new child").hexdigest()))
        _apply_member_plan(installer, plan, home, skills)
        assert not (skills / "analyst" / "agents" / "openai.yaml").exists()
        assert installer._InstallTransaction._point_matches(skills / "analyst" / "agents", container)
        assert (skills / "analyst" / "assets" / "body.txt").read_bytes() == b"selected new child"
        members = json.loads(receipt.read_bytes())["skills"]["analyst"]["members"]
        assert "agents" not in members and "agents/openai.yaml" not in members
        assert members["assets"] == "directory"
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_member_partial_write_retains_original_failure_and_restores_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer, source, home, skills, _receipt = _member_fixture(tmp_path)
    before = _inventory(skills)
    physical = installer._InstallTransaction._observe(skills / "analyst")
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                                member_selection=(("analyst", ("SKILL.md",)),))
    original = installer._InstallTransaction._write_owned_file
    def fail_partial(self, path, descriptor, chunks, record, digest, **kwargs):
        if path.parent != skills / "analyst":
            return original(self, path, descriptor, chunks, record, digest, **kwargs)
        def interrupted():
            yield b"partial selected bytes"
            raise OSError("injected member partial write")
        return original(self, path, descriptor, interrupted(), record, digest, **kwargs)
    monkeypatch.setattr(installer._InstallTransaction, "_write_owned_file", fail_partial)
    try:
        with pytest.raises(OSError, match="injected member partial write"):
            _apply_member_plan(installer, plan, home, skills)
        assert _inventory(skills) == before
        assert installer._InstallTransaction._image_matches(skills / "analyst", physical)
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_member_failed_descriptor_close_attempts_final_closer_and_restores_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer, source, home, skills, _receipt = _member_fixture(tmp_path)
    before = _inventory(skills)
    physical = installer._InstallTransaction._observe(skills / "analyst")
    plan = installer._preflight_canonical_skills(source, skills, root=ROOT, global_install=True,
                                                member_selection=(("analyst", ("SKILL.md",)),))
    original_write = installer._InstallTransaction._write_owned_file
    original_close = installer.os.close
    captured = {"descriptor": None, "attempts": 0}
    def capture(self, path, descriptor, *args, **kwargs):
        result = original_write(self, path, descriptor, *args, **kwargs)
        if path.parent == skills / "analyst":
            captured["descriptor"] = descriptor
        return result
    def fail_first_close(descriptor):
        if descriptor == captured["descriptor"]:
            captured["attempts"] += 1
            if captured["attempts"] == 1:
                raise OSError("injected member descriptor close")
        return original_close(descriptor)
    monkeypatch.setattr(installer._InstallTransaction, "_write_owned_file", capture)
    monkeypatch.setattr(installer.os, "close", fail_first_close)
    try:
        with pytest.raises(OSError, match="injected member descriptor close"):
            _apply_member_plan(installer, plan, home, skills)
        assert captured["attempts"] >= 2
        assert _inventory(skills) == before
        assert installer._InstallTransaction._image_matches(skills / "analyst", physical)
    finally:
        installer._discard_canonical_skills_plan(plan)
