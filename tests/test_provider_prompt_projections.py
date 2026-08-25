from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import tarfile
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate-provider-prompt-projections.py"
INSTALLER_PATH = ROOT / "scripts" / "production_installer.py"
TRANSPORT_FILES = (
    "provider_prompt.py",
    "invoke-codex-prompt.py",
    "invoke-claude-prompt.py",
    "invoke-kimi-prompt.py",
    "invoke-grok-prompt.py",
    "external-prompt-governance.md",
)


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "slice_b_provider_prompt_projection_validator", VALIDATOR_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_installer():
    spec = importlib.util.spec_from_file_location(
        "slice_b_provider_prompt_projection_installer", INSTALLER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_source_manifest_binds_the_generated_governance_capsule() -> None:
    """Catches a projection manifest that ships a composer without its policy input."""

    validator = _load_validator()
    result = validator.validate_source_manifest(
        ROOT / "shared" / "provider-prompt-projections.v1.json", ROOT
    )

    assert result["files"] == [
        "provider_prompt.py",
        "invoke-codex-prompt.py",
        "invoke-claude-prompt.py",
        "invoke-kimi-prompt.py",
        "invoke-grok-prompt.py",
        "external-prompt-governance.md",
    ]


def test_source_manifest_binds_approved_codex_and_claude_thin_wrappers() -> None:
    """Catches a host install that has no callable wrapper-owned prompt entrypoint."""

    manifest = json.loads(
        (ROOT / "shared" / "provider-prompt-projections.v1.json").read_text(
            encoding="utf-8"
        )
    )
    for name in ("invoke-codex-prompt.py", "invoke-claude-prompt.py"):
        assert manifest["files"][name]["source"] == f"scripts/{name}"
        assert (ROOT / "scripts" / name).is_file()


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _linked_global_claude(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, installer
) -> tuple[Path, Path]:
    """Create the only admitted linked-subroot shape over a seeded pack."""

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    assert installer.install("claude", ["--global", "--no-hypothesis-hook"]) == 0
    logical = home / ".claude"
    backing = tmp_path / "linked-claude"
    backing.mkdir()
    try:
        for name in ("agents", "skills", "commands"):
            destination = backing / name
            shutil.move(str(logical / name), str(destination))
            os.symlink(destination, logical / name, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")
    return logical, backing


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    source = tmp_path / "source"
    canonical = tmp_path / "canonical" / "scripts"
    claude = tmp_path / "claude" / "agents" / "scripts"
    for directory in (source / "scripts", canonical, claude):
        directory.mkdir(parents=True)
    files: dict[str, dict[str, object]] = {}
    for name in TRANSPORT_FILES:
        payload = f"# {name}\n".encode()
        (source / "scripts" / name).write_bytes(payload)
        (canonical / name).write_bytes(payload)
        (claude / name).write_bytes(payload)
        files[name] = {
            "source": f"scripts/{name}",
            "sha256": _sha(payload),
            "destination": f"scripts/{name}",
        }
    manifest = tmp_path / "provider-prompt-projections.v1.json"
    manifest_text = json.dumps(
        {
            "schemaVersion": 1,
            "packRevision": "1.x-slice-b",
            "files": files,
        },
        indent=2,
    ) + "\n"
    manifest.write_text(manifest_text, encoding="utf-8")
    (source / "shared").mkdir()
    capsule = (source / "scripts" / "external-prompt-governance.md").read_bytes()
    (source / "shared" / "AGENTS.shared.md").write_bytes(
        b"before\n"
        b"<!-- BEGIN ORCHESTRARIUM EXTERNAL GOVERNANCE V1 -->\n"
        + capsule
        + b"<!-- END ORCHESTRARIUM EXTERNAL GOVERNANCE V1 -->\n"
        + b"after\n"
    )
    (source / "shared" / "provider-prompt-projections.v1.json").write_text(
        manifest_text, encoding="utf-8"
    )
    shutil.copyfile(
        VALIDATOR_PATH,
        source / "scripts" / "validate-provider-prompt-projections.py",
    )
    return source, canonical, claude, manifest


def _run_scoped_validator(
    scope: str, source_root: Path, install_root: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            "--require",
            "--scope",
            scope,
            "--source-root",
            str(source_root),
            "--install-root",
            str(install_root),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=os.environ.copy(),
    )


def test_complete_manifest_accepts_byte_identical_two_home_projections(
    tmp_path: Path,
) -> None:
    validator = _load_validator()
    source, canonical, claude, manifest = _fixture(tmp_path)
    result = validator.validate_projection_manifest(
        manifest,
        source,
        (("canonical", canonical), ("claude-host", claude)),
    )
    assert result["packRevision"] == "1.x-slice-b"
    assert result["files"] == list(TRANSPORT_FILES)
    assert result["projections"] == ["canonical", "claude-host"]


def test_project_scope_uses_its_paired_projections_without_reading_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A project health check must not be coupled to unrelated global bytes."""

    source, _canonical, _claude, _manifest = _fixture(tmp_path)
    project = tmp_path / "project"
    canonical = project / ".agents" / "skills" / "lead" / "scripts"
    claude = project / ".claude" / "agents" / "scripts"
    for destination in (canonical, claude):
        destination.mkdir(parents=True)
        for name in TRANSPORT_FILES:
            shutil.copyfile(source / "scripts" / name, destination / name)
    home = tmp_path / "poisoned-home"
    poisoned = home / ".agents" / "skills" / "lead" / "scripts"
    poisoned.mkdir(parents=True)
    (poisoned / TRANSPORT_FILES[0]).write_text("global drift\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("USERPROFILE", raising=False)

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            "--require",
            "--scope",
            "project",
            "--install-root",
            str(project),
            "--source-root",
            str(source),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=os.environ.copy(),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert '"projections":["canonical","claude-host"]' in result.stdout


def test_source_scope_validates_only_the_named_source_root(tmp_path: Path) -> None:
    source, _canonical, _claude, _manifest = _fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            "--require",
            "--scope",
            "source",
            "--source-root",
            str(source),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"projections":[]' in result.stdout


def test_global_scope_uses_the_named_install_root_not_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, _canonical, _claude, _manifest = _fixture(tmp_path)
    global_root = tmp_path / "global-install"
    for destination in (
        global_root / ".agents" / "skills" / "lead" / "scripts",
        global_root / ".claude" / "agents" / "scripts",
    ):
        destination.mkdir(parents=True)
        for name in TRANSPORT_FILES:
            shutil.copyfile(source / "scripts" / name, destination / name)
    monkeypatch.setenv("HOME", str(tmp_path / "poisoned-home"))
    monkeypatch.delenv("USERPROFILE", raising=False)
    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            "--require",
            "--scope",
            "global",
            "--source-root",
            str(source),
            "--install-root",
            str(global_root),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"projections":["canonical","claude-host"]' in result.stdout


def test_global_scope_accepts_installer_authorized_linked_claude_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = _load_installer()
    logical, _backing = _linked_global_claude(tmp_path, monkeypatch, installer)

    result = _run_scoped_validator("global", ROOT, logical.parent)

    assert result.returncode == 0, result.stdout + result.stderr
    assert '"projections":["canonical","claude-host"]' in result.stdout


def test_linked_runtime_subroots_helper_is_pinned_to_canonical_digest() -> None:
    validator = _load_validator()
    expected_digest = "a2194fcb49b26e354552279d03b00e2e3bf1231268e0948070949fc411a8a432"

    assert validator._LINKED_RUNTIME_SUBROOTS_SHA256 == expected_digest
    assert _sha((ROOT / "scripts" / "linked_runtime_subroots.py").read_bytes()) == expected_digest


def test_linked_runtime_subroots_digest_mismatch_rejects_before_side_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validator = _load_validator()
    marker = tmp_path / "unexpected-side-effect.txt"
    helper = tmp_path / "linked_runtime_subroots.py"
    helper.write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(validator, "__file__", str(tmp_path / "validator.py"))

    with pytest.raises(
        validator.ProjectionParityError,
        match="E_TRANSPORT_PROJECTION_PARITY: Claude linked runtime authority digest drift",
    ):
        validator._linked_runtime_subroots_module()

    assert not marker.exists()


def test_linked_runtime_subroots_executes_attested_bytes_without_pathname_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validator = _load_validator()
    helper = tmp_path / "linked_runtime_subroots.py"
    helper.write_bytes((ROOT / "scripts" / "linked_runtime_subroots.py").read_bytes())
    marker = tmp_path / "pathname-reopened.txt"
    monkeypatch.setattr(validator, "__file__", str(tmp_path / "validator.py"))
    original_read_bytes = validator._BoundOrdinaryFile.read_bytes
    retargeted = False

    def retarget_after_attested_read(bound):
        nonlocal retargeted
        payload = original_read_bytes(bound)
        if bound.path == helper:
            helper.write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('reopened')\n",
                encoding="utf-8",
            )
            retargeted = True
        return payload

    monkeypatch.setattr(
        validator._BoundOrdinaryFile, "read_bytes", retarget_after_attested_read
    )
    module_name = "_orchestrarium_provider_prompt_linked_runtime_subroots"
    sys.modules.pop(module_name, None)
    try:
        module = validator._linked_runtime_subroots_module()
    finally:
        sys.modules.pop(module_name, None)

    assert retargeted is True
    assert hasattr(module, "LinkedRuntimeSubrootAuthority")
    assert not marker.exists()


def test_project_scope_rejects_linked_claude_agents_even_when_the_link_is_global_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = _load_installer()
    logical, _backing = _linked_global_claude(tmp_path, monkeypatch, installer)

    result = _run_scoped_validator("project", ROOT, logical.parent)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.startswith("E_TRANSPORT_PROJECTION_PARITY:")


def test_linked_global_claude_authority_cannot_be_reused_for_a_wrong_projection_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validator = _load_validator()
    installer = _load_installer()
    logical, _backing = _linked_global_claude(tmp_path, monkeypatch, installer)
    authority = validator._bind_global_claude_agents_authority(logical.parent)
    assert authority is not None

    with pytest.raises(
        validator.ProjectionParityError,
        match="E_TRANSPORT_PROJECTION_PARITY: linked Claude authority projection root",
    ):
        validator.validate_projection_manifest(
            ROOT / "shared" / "provider-prompt-projections.v1.json",
            ROOT,
            (
                ("canonical", logical.parent / ".agents" / "skills" / "lead" / "scripts"),
                ("claude-host", tmp_path / "wrong-root" / "scripts"),
            ),
            claude_agents_authority=authority,
        )


def test_global_scope_rejects_linked_leaf_below_authorized_claude_agents_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = _load_installer()
    logical, backing = _linked_global_claude(tmp_path, monkeypatch, installer)
    leaf = backing / "agents" / "scripts" / TRANSPORT_FILES[0]
    replacement = tmp_path / "linked-provider-prompt.py"
    shutil.copyfile(leaf, replacement)
    leaf.unlink()
    try:
        os.symlink(replacement, leaf)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"file symlink unavailable: {exc}")

    result = _run_scoped_validator("global", ROOT, logical.parent)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.startswith("E_TRANSPORT_PROJECTION_PARITY:")


def test_global_scope_rejects_claude_agents_retarget_during_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    validator = _load_validator()
    installer = _load_installer()
    logical, backing = _linked_global_claude(tmp_path, monkeypatch, installer)
    alternate = tmp_path / "alternate-agents"
    shutil.copytree(backing / "agents", alternate)
    original = validator._validate_bound_bytes
    retargeted = False

    def retarget_after_all_handles_are_bound(bound, digest, label):
        nonlocal retargeted
        result = original(bound, digest, label)
        if label == "source/provider_prompt.py":
            (logical / "agents").unlink()
            os.symlink(alternate, logical / "agents", target_is_directory=True)
            retargeted = True
        return result

    monkeypatch.setattr(
        validator, "_validate_bound_bytes", retarget_after_all_handles_are_bound
    )

    assert validator.main(
        [
            "--require",
            "--scope",
            "global",
            "--source-root",
            str(ROOT),
            "--install-root",
            str(logical.parent),
        ]
    ) == 1
    assert retargeted is True
    assert capsys.readouterr().err.startswith("E_TRANSPORT_PROJECTION_PARITY:")


def test_bare_projection_require_is_rejected_as_ambiguous(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(VALIDATOR_PATH), "--require"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=tmp_path,
    )
    assert result.returncode == 1
    assert result.stderr.startswith("E_TRANSPORT_PROJECTION_PARITY: explicit scope is required")


def test_parent_symlink_is_rejected_before_projection_bytes_are_read(
    tmp_path: Path,
) -> None:
    """A redirected directory must not be attested as a local projection."""

    validator = _load_validator()
    source, canonical, claude, manifest = _fixture(tmp_path)
    redirected_parent = tmp_path / "redirected-canonical"
    try:
        os.symlink(canonical.parent, redirected_parent, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory symlink unavailable: {exc}")

    with pytest.raises(validator.ProjectionParityError, match="E_TRANSPORT_PROJECTION_PARITY"):
        validator.validate_projection_manifest(
            manifest,
            source,
            (("canonical", redirected_parent / "scripts"), ("claude-host", claude)),
        )


@pytest.mark.parametrize("failure", ("missing", "drift", "manifest", "cross-host"))
def test_every_projection_violation_uses_one_stable_id(
    tmp_path: Path, failure: str
) -> None:
    source, canonical, claude, manifest = _fixture(tmp_path)
    if failure == "missing":
        (canonical / TRANSPORT_FILES[0]).unlink()
    elif failure == "drift":
        (claude / TRANSPORT_FILES[1]).write_text("drift\n", encoding="utf-8")
    elif failure == "manifest":
        data = json.loads(manifest.read_text(encoding="utf-8"))
        del data["files"][TRANSPORT_FILES[2]]
        manifest.write_text(json.dumps(data), encoding="utf-8")
    else:
        (claude / TRANSPORT_FILES[0]).write_text(
            "from scripts.provider_prompt import launch\n", encoding="utf-8"
        )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR_PATH),
            "--require",
            "--manifest",
            str(manifest),
            "--source-root",
            str(source),
            "--projection",
            f"canonical={canonical}",
            "--projection",
            f"claude-host={claude}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.startswith("E_TRANSPORT_PROJECTION_PARITY:")


def test_claude_projection_stage_has_one_create_only_apply_path(tmp_path: Path) -> None:
    installer = _load_installer()
    source, canonical, claude, _manifest = _fixture(tmp_path)
    for name in TRANSPORT_FILES:
        (claude / name).unlink()

    class Recorder:
        anchor = tmp_path

        def __init__(self) -> None:
            self.calls: list[tuple[Path, bytes]] = []

        def create_file(self, relative: Path, payload: bytes) -> None:
            self.calls.append((relative, payload))

    recorder = Recorder()
    stage = installer._stage_claude_transport_projection(source, canonical, claude)
    installer._apply_claude_transport_projection(stage, claude, recorder)
    assert recorder.calls == [
        (
            claude.relative_to(tmp_path) / name,
            (source / "scripts" / name).read_bytes(),
        )
        for name in TRANSPORT_FILES
    ] + [
        (
            claude.relative_to(tmp_path).parent
            / "shared"
            / "provider-prompt-projections.v1.json",
            (source / "shared" / "provider-prompt-projections.v1.json").read_bytes(),
        )
    ]


@pytest.mark.parametrize(
    ("state", "expected_names"),
    (
        ("absent", TRANSPORT_FILES),
        ("current", ()),
    ),
)
def test_claude_transport_preflight_admits_only_atomic_projection_states(
    tmp_path: Path, state: str, expected_names: tuple[str, ...]
) -> None:
    installer = _load_installer()
    source, canonical, claude, _manifest = _fixture(tmp_path)
    for name in TRANSPORT_FILES:
        (claude / name).unlink()
    if state == "current":
        for name in TRANSPORT_FILES:
            (claude / name).write_bytes((source / "scripts" / name).read_bytes())
        (claude.parent / "shared").mkdir(parents=True)
        (claude.parent / "shared" / "provider-prompt-projections.v1.json").write_bytes(
            (source / "shared" / "provider-prompt-projections.v1.json").read_bytes()
        )
    staged = installer._stage_claude_transport_projection(source, canonical, claude)
    assert tuple(name for name, _payload in staged.pending_files) == expected_names


def test_claude_transport_preflight_accepts_only_true_e7_legacy_singleton(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    canonical = tmp_path / "canonical"
    projection = tmp_path / "claude" / "agents" / "scripts"
    canonical.mkdir(parents=True)
    projection.mkdir(parents=True)
    for name in TRANSPORT_FILES:
        (canonical / name).write_bytes((ROOT / "scripts" / name).read_bytes())
    legacy = subprocess.run(
        ["git", "show", "e7a691dea4f1d3cb154d338c63b274ebcd74ee4c:src.claude/agents/scripts/provider_prompt.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    assert hashlib.sha256(legacy).hexdigest() == installer.E7_LEGACY_PROVIDER_PROMPT_SHA256
    (projection / "provider_prompt.py").write_bytes(legacy)
    for name in ("invoke-codex-prompt.py", "invoke-claude-prompt.py"):
        (projection / name).write_bytes((ROOT / "scripts" / name).read_bytes())

    staged = installer._stage_claude_transport_projection(ROOT, canonical, projection)

    assert staged.replace_legacy_singleton is True
    assert tuple(name for name, _payload in staged.pending_files) == TRANSPORT_FILES


def test_claude_transport_preflight_accepts_the_published_pre_e7_singleton(
    tmp_path: Path,
) -> None:
    """The explicitly pinned published predecessor may upgrade, nothing else may."""

    installer = _load_installer()
    canonical = tmp_path / "canonical"
    projection = tmp_path / "claude" / "agents" / "scripts"
    canonical.mkdir(parents=True)
    projection.mkdir(parents=True)
    for name in TRANSPORT_FILES:
        (canonical / name).write_bytes((ROOT / "scripts" / name).read_bytes())
    legacy = subprocess.run(
        ["git", "show", "8b9fce435853e1988c449805786c9ce9cbf9579e:src.claude/agents/scripts/provider_prompt.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    assert hashlib.sha256(legacy).hexdigest() == installer.PRE_E7_LEGACY_PROVIDER_PROMPT_SHA256
    (projection / "provider_prompt.py").write_bytes(legacy)
    for name in ("invoke-codex-prompt.py", "invoke-claude-prompt.py"):
        (projection / name).write_bytes((ROOT / "scripts" / name).read_bytes())

    staged = installer._stage_claude_transport_projection(ROOT, canonical, projection)

    assert staged.replace_legacy_singleton is True
    assert tuple(name for name, _payload in staged.pending_files) == TRANSPORT_FILES


def test_e7_six_tree_upgrade_rolls_back_after_middle_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The accepted-prior e7 tree upgrade is all-or-nothing under a mid-flight fault."""

    installer = _load_installer()
    snapshot = tmp_path / "e7-source"
    snapshot.mkdir()
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "e7a691dea4f1d3cb154d338c63b274ebcd74ee4c"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as package:
        package.extractall(snapshot, filter="data")
    target = tmp_path / "target"
    target.mkdir()
    seeded = subprocess.run(
        [
            sys.executable, str(snapshot / "scripts" / "install-codex.py"),
            "--target", str(target), "--force", "--allow-unsafe-target",
            "--no-hypothesis-hook",
        ],
        cwd=snapshot,
        capture_output=True,
        text=True,
    )
    assert seeded.returncode == 0, seeded.stdout + seeded.stderr
    canonical = target / ".agents" / "skills"
    before = {
        path.relative_to(canonical).as_posix(): path.read_bytes()
        for path in canonical.rglob("*") if path.is_file()
    }
    original = installer._CreateOnlyMutablePath.replace_exact_tree
    calls = 0

    def fail_after_middle(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        result = original(self, *args, **kwargs)
        if calls == 3:
            raise RuntimeError("injected six-tree replacement failure")
        return result

    monkeypatch.setattr(
        installer._CreateOnlyMutablePath, "replace_exact_tree", fail_after_middle
    )
    result = installer.install(
        "codex",
        ["--target", str(target), "--force", "--allow-unsafe-target", "--no-hypothesis-hook"],
    )
    after = {
        path.relative_to(canonical).as_posix(): path.read_bytes()
        for path in canonical.rglob("*") if path.is_file()
    }
    assert result == 1
    assert calls == 3
    assert after == before


def test_e7_claude_transport_replacement_rolls_back_trees_trio_and_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A post-transport fault restores both accepted-prior surfaces exactly."""

    installer = _load_installer()
    snapshot = tmp_path / "e7-source"
    snapshot.mkdir()
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "e7a691dea4f1d3cb154d338c63b274ebcd74ee4c"],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as package:
        package.extractall(snapshot, filter="data")
    target = tmp_path / "target"
    target.mkdir()
    seeded = subprocess.run(
        [sys.executable, str(snapshot / "scripts" / "install-claude.py"), "--target", str(target), "--force", "--allow-unsafe-target", "--no-hypothesis-hook"],
        cwd=snapshot, capture_output=True, text=True,
    )
    assert seeded.returncode == 0, seeded.stdout + seeded.stderr
    canonical = target / ".agents" / "skills"
    transport = target / ".claude" / "agents" / "scripts"
    manifest = transport.parent / "shared" / "provider-prompt-projections.v1.json"
    before_trees = {path.relative_to(canonical).as_posix(): path.read_bytes() for path in canonical.rglob("*") if path.is_file()}
    before_transport = {name: (transport / name).read_bytes() if (transport / name).is_file() else None for name in TRANSPORT_FILES}
    before_manifest = manifest.read_bytes() if manifest.is_file() else None
    original = installer._CreateOnlyMutablePath.replace_exact_file

    def fail_after_transport(self, relative, expected_digest, payload):
        result = original(self, relative, expected_digest, payload)
        if Path(relative).name == "provider_prompt.py":
            raise RuntimeError("injected post-transport replacement failure")
        return result

    monkeypatch.setattr(installer._CreateOnlyMutablePath, "replace_exact_file", fail_after_transport)
    result = installer.install("claude", ["--target", str(target), "--force", "--allow-unsafe-target", "--no-hypothesis-hook"])
    after_trees = {path.relative_to(canonical).as_posix(): path.read_bytes() for path in canonical.rglob("*") if path.is_file()}
    after_transport = {name: (transport / name).read_bytes() if (transport / name).is_file() else None for name in TRANSPORT_FILES}
    after_manifest = manifest.read_bytes() if manifest.is_file() else None
    assert result == 1
    assert after_trees == before_trees
    assert after_transport == before_transport
    assert after_manifest == before_manifest


def test_claude_transport_preflight_rejects_mixed_state_before_apply(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    source, canonical, claude, _manifest = _fixture(tmp_path)
    for name in TRANSPORT_FILES:
        (claude / name).unlink()
    (claude / TRANSPORT_FILES[0]).write_bytes(
        (source / "scripts" / TRANSPORT_FILES[0]).read_bytes()
    )
    (claude / TRANSPORT_FILES[1]).write_text("drift\n", encoding="utf-8")

    with pytest.raises(ValueError, match="E_TRANSPORT_PROJECTION_PARITY"):
        installer._stage_claude_transport_projection(source, canonical, claude)


def test_canonical_preflight_rejects_late_transport_collision_before_any_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Claude collision must stop every canonical-skill write, not roll it back."""

    installer = _load_installer()
    canonical = tmp_path / ".agents" / "skills"
    claude = tmp_path / ".claude" / "agents" / "scripts"
    claude.mkdir(parents=True)

    class MutationSpy:
        anchor = tmp_path
        dry_run = False

        def __init__(self) -> None:
            self.calls: list[str] = []

        def create_tree(self, *_args, **_kwargs) -> None:
            self.calls.append("create_tree")
            raise AssertionError("canonical write before complete preflight")

        def replace_exact_tree(self, *_args, **_kwargs) -> None:
            self.calls.append("replace_exact_tree")
            raise AssertionError("canonical write before complete preflight")

        def create_file(self, *_args, **_kwargs) -> None:
            self.calls.append("create_file")
            raise AssertionError("canonical write before complete preflight")

        def replace_exact_file(self, *_args, **_kwargs) -> None:
            self.calls.append("replace_exact_file")
            raise AssertionError("canonical write before complete preflight")

    def reject_late_transport(*_args, **_kwargs):
        raise ValueError("E_TRANSPORT_PROJECTION_PARITY: atomic projection state")

    monkeypatch.setattr(
        installer, "_stage_claude_transport_projection", reject_late_transport
    )
    owner = MutationSpy()

    with pytest.raises(ValueError, match="E_TRANSPORT_PROJECTION_PARITY"):
        installer._install_canonical_skills(
            ROOT / "src.codex" / "skills",
            canonical,
            owner,
            root=ROOT,
            claude_transport_root=claude,
        )
    assert owner.calls == []


def test_immutable_canonical_plan_rejects_post_preflight_drift_before_write(
    tmp_path: Path,
) -> None:
    """Applying a retained plan must fail before owner calls if a member changes."""

    installer = _load_installer()
    canonical = tmp_path / ".agents" / "skills"

    class MutationSpy:
        anchor = tmp_path
        dry_run = False

        def __init__(self) -> None:
            self.calls: list[str] = []

        def create_tree(self, *_args, **_kwargs) -> None:
            self.calls.append("create_tree")

        def replace_exact_tree(self, *_args, **_kwargs) -> None:
            self.calls.append("replace_exact_tree")

    plan = installer._preflight_canonical_skills(
        ROOT / "src.codex" / "skills", canonical, root=ROOT
    )
    try:
        drift = canonical / "accessibility-reviewer"
        drift.mkdir(parents=True)
        (drift / "unowned.txt").write_text("collision\n", encoding="utf-8")
        owner = MutationSpy()

        with pytest.raises(ValueError, match="E_ACCEPTED_PRIOR_COLLISION: preflight drift"):
            installer._apply_canonical_skills_plan(plan, canonical, owner, root=ROOT)
        assert owner.calls == []
    finally:
        installer._discard_canonical_skills_plan(plan)


def test_canonical_stage_publishes_and_validates_transport_before_skill_projection(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    canonical = tmp_path / "canonical" / ".agents" / "skills"
    claude = tmp_path / "claude" / "agents" / "scripts"
    claude.mkdir(parents=True)
    transaction = installer._InstallTransaction([], enabled=False)
    owner = installer._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)

    installer._install_canonical_skills(
        ROOT / "src.codex" / "skills",
        canonical,
        owner,
        root=ROOT,
        claude_transport_root=claude,
    )

    assert not hasattr(installer, "_install_claude_transport_projections")
    for name in TRANSPORT_FILES:
        expected = (ROOT / "scripts" / name).read_bytes()
        assert (canonical / "lead" / "scripts" / name).read_bytes() == expected
        assert (claude / name).read_bytes() == expected
    assert (
        claude.parent / "shared" / "provider-prompt-projections.v1.json"
    ).read_bytes() == (ROOT / "shared" / "provider-prompt-projections.v1.json").read_bytes()


def test_global_claude_declared_linked_subroots_are_bound_and_dry_run_is_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = _load_installer()
    logical, backing = _linked_global_claude(tmp_path, monkeypatch, installer)
    before = {name: _tree_bytes(backing / name) for name in ("agents", "skills", "commands")}
    links = {name: os.readlink(logical / name) for name in before}

    observed = {}
    for name in ("agents", "skills", "commands"):
        resolved, authority = installer._resolve_global_claude_linked_subroot(
            ROOT, logical, "global", name
        )
        assert os.path.samefile(resolved, backing / name)
        assert authority is not None
        assert authority.name == name
        assert authority.logical_root == logical / name
        assert os.path.samefile(authority.resolved_root, backing / name)
        assert authority.link_chain[0][2] == links[name]
        observed[name] = authority

    assert installer.install(
        "claude", ["--global", "--dry-run", "--no-hypothesis-hook"]
    ) == 0
    assert {name: os.readlink(logical / name) for name in before} == links
    assert {name: _tree_bytes(backing / name) for name in before} == before
    for authority in observed.values():
        installer._assert_global_claude_linked_subroot_authority(ROOT, authority)


def test_linked_claude_subroot_is_rejected_outside_global_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = _load_installer()
    logical, _backing = _linked_global_claude(tmp_path, monkeypatch, installer)

    with pytest.raises(ValueError, match="E_MUTABLE_PATH_REPARSE"):
        installer._resolve_global_claude_linked_subroot(ROOT, logical, "target", "agents")


def test_linked_claude_subroot_retarget_fails_before_apply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = _load_installer()
    logical, backing = _linked_global_claude(tmp_path, monkeypatch, installer)
    _resolved, authority = installer._resolve_global_claude_linked_subroot(
        ROOT, logical, "global", "agents"
    )
    assert authority is not None
    alternate = tmp_path / "alternate-agents"
    shutil.copytree(backing / "agents", alternate)
    (logical / "agents").unlink()
    os.symlink(alternate, logical / "agents", target_is_directory=True)

    with pytest.raises(ValueError, match="E_MUTABLE_PATH_IDENTITY_CHANGED"):
        installer._assert_global_claude_linked_subroot_authority(ROOT, authority)


def test_linked_claude_subroot_rollback_restores_resolved_agent_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = _load_installer()
    logical, backing = _linked_global_claude(tmp_path, monkeypatch, installer)
    marker = backing / "agents" / "consultant.md"
    original = marker.read_bytes()
    marker.write_bytes(b"custom linked agent before transaction\n")
    links = {name: os.readlink(logical / name) for name in ("agents", "skills", "commands")}
    sync_tree = installer._sync_tree

    def fail_after_commands(source: Path, target: Path, dry_run: bool, **kwargs) -> None:
        sync_tree(source, target, dry_run, **kwargs)
        if source.name == "commands":
            raise RuntimeError("injected linked-subroot failure")

    monkeypatch.setattr(installer, "_sync_tree", fail_after_commands)
    assert installer.install("claude", ["--global", "--no-hypothesis-hook"]) == 1
    assert marker.read_bytes() == b"custom linked agent before transaction\n"
    assert original != marker.read_bytes()
    assert {name: os.readlink(logical / name) for name in links} == links


def test_only_exact_historical_claude_skill_tree_may_migrate_to_projection(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    canonical_source = tmp_path / "canonical-source"
    historical_source = tmp_path / "historical-source"
    canonical_target = tmp_path / "canonical-target"
    projection_root = tmp_path / "claude-skills"
    for root, payload in (
        (canonical_source, b"canonical\n"),
        (historical_source, b"historical\n"),
        (canonical_target, b"canonical\n"),
        (projection_root, b"historical\n"),
    ):
        leaf = root / "analyst"
        leaf.mkdir(parents=True)
        (leaf / "SKILL.md").write_bytes(payload)

    plan = installer._preflight_claude_skill_projections(
        canonical_source, historical_source, canonical_target, projection_root
    )
    assert plan[0].action == "migrate"
    transaction = installer._InstallTransaction([], enabled=False)
    owner = installer._CreateOnlyMutablePath(projection_root, transaction, dry_run=False)
    installer._apply_claude_skill_projection_plan(
        plan, canonical_source, projection_root, owner
    )
    assert os.path.samefile(projection_root / "analyst", canonical_target / "analyst")

    (projection_root / "analyst").unlink()
    (projection_root / "analyst").mkdir()
    (projection_root / "analyst" / "SKILL.md").write_text("untrusted\n", encoding="utf-8")
    with pytest.raises(ValueError, match="E_CREATE_ONLY_PROJECTION_COLLISION"):
        installer._preflight_claude_skill_projections(
            canonical_source, historical_source, canonical_target, projection_root
        )
