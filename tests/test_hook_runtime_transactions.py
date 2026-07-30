"""Python-installer transaction, confinement, and interruption tests."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".scratch"
HELPER_PATH = ROOT / "scripts/install-hypothesis-hook.py"
PRODUCTION_INSTALLER_PATH = ROOT / "scripts/production_installer.py"


def _load_helper():
    spec = importlib.util.spec_from_file_location(
        "hook_installer_for_transactions", HELPER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hook_installer = _load_helper()


def _load_production_installer():
    spec = importlib.util.spec_from_file_location(
        "production_installer_for_transactions",
        PRODUCTION_INSTALLER_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


production_installer = _load_production_installer()
ABORT_ENV = hook_installer.TEST_TRANSACTION_ABORT_ENV
ABORT_EXIT = hook_installer.TEST_TRANSACTION_ABORT_EXIT


@dataclass(frozen=True)
class Case:
    provider: str
    script: Path
    config: str
    installed_root: str


CASES = (
    Case(
        "codex",
        ROOT / "scripts/install-codex.py",
        ".codex/hooks.json",
        ".agents/skills/lead",
    ),
    Case(
        "claude",
        ROOT / "scripts/install-claude.py",
        ".claude/settings.json",
        ".claude/agents",
    ),
)


def _install(case: Case, project: Path, abort_after: str | None = None):
    env = os.environ.copy()
    env.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
    env.pop(ABORT_ENV, None)
    if abort_after:
        env[ABORT_ENV] = abort_after
    return subprocess.run(
        [
            sys.executable,
            str(case.script),
            "--target",
            str(project),
            "--force",
            "--allow-unsafe-target",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=240,
    )


def _commands(config: Path) -> list[str]:
    data = json.loads(config.read_text(encoding="utf-8"))
    commands: list[str] = []
    for entries in data["hooks"].values():
        for entry in entries:
            for hook in entry.get("hooks", ()):
                commands.append(hook["command"])
                commands.extend(hook.get("args", ()))
    return commands


def _tree_snapshot(root: Path) -> tuple[tuple[str, str, str], ...]:
    entries: list[tuple[str, str, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            entries.append((relative, "symlink", os.readlink(path)))
        elif path.is_file():
            entries.append(
                (
                    relative,
                    "file",
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                )
            )
        elif path.is_dir():
            entries.append((relative, "dir", ""))
    return tuple(entries)


def _seed_unrelated_provider_state(project: Path, case: Case) -> tuple[Path, ...]:
    provider_root = project / f".{case.provider}"
    unrelated = (
        provider_root / "sessions" / "session-state.bin",
        provider_root / "vendor_imports" / "vendor-state.bin",
    )
    for index, path in enumerate(unrelated):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"unrelated-{index}".encode("ascii"))
    custom = (
        project / ".agents" / "skills" / "lead" / "user-custom.txt"
        if case.provider == "codex"
        else provider_root / "agents" / "user-custom.txt"
    )
    custom.parent.mkdir(parents=True, exist_ok=True)
    custom.write_text("preserve custom sibling\n", encoding="utf-8")
    return (*unrelated, custom)


def _make_file_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=False)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")
    assert link.is_symlink()


def _policy_owner_count(source: str) -> int:
    tree = ast.parse(source)
    return sum(
        isinstance(node, ast.ClassDef) and node.name == "TestAbortPolicy"
        for node in ast.walk(tree)
    )


def _assert_no_abort_env_reads(sources: dict[Path, str]) -> None:
    offenders = [path for path, text in sources.items() if ABORT_ENV in text]
    assert offenders == []


def _assert_no_second_stage_owner(sources: dict[Path, str]) -> None:
    stage_tuple = '("sync", "register", "verify", "reclaim")'
    offenders = [path for path, text in sources.items() if stage_tuple in text]
    assert offenders == []


def _checkpoint(
    target: Path,
    *,
    stage: str = "sync",
    requested: str | None = None,
    pytest_provenance: bool = True,
    install_scope: str = "target",
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop(ABORT_ENV, None)
    env.pop("PYTEST_CURRENT_TEST", None)
    if requested is not None:
        env[ABORT_ENV] = requested
    if pytest_provenance:
        env["PYTEST_CURRENT_TEST"] = "controlled-test-only-seam"
    return subprocess.run(
        [
            sys.executable,
            str(HELPER_PATH),
            "--target",
            str(target),
            "--platform",
            "codex",
            "--host-os",
            "windows" if os.name == "nt" else "posix",
            "--repo-root",
            str(ROOT),
            "--test-install-scope",
            install_scope,
            "--test-transaction-checkpoint",
            stage,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )


def _seed_reclaim_fixture(
    project: Path, case: Case
) -> tuple[Path, Path, tuple[Path, ...]]:
    installed = project / case.installed_root
    provider_root = ROOT / (
        "src.codex/skills/lead"
        if case.provider == "codex"
        else "src.claude/agents"
    )
    candidates: list[Path] = []
    for source in hook_installer.owned_hook_wrapper_sources(ROOT, case.provider):
        target = installed / source.relative_to(provider_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        shutil.copy2(source.with_suffix(".py"), target.with_suffix(".py"))
        candidates.append(target)

    entries = []
    for path in candidates:
        if case.provider == "claude":
            hook = {
                "type": "command",
                "command": str(Path(sys.executable).resolve()),
                "args": [str(path.with_suffix(".py").resolve())],
            }
        else:
            hook = {
                "type": "command",
                "command": (
                    f"{Path(sys.executable).resolve()} "
                    f"{path.with_suffix('.py').resolve()}"
                ),
            }
        entries.append({"hooks": [hook]})
    config = project / case.config
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        json.dumps({"hooks": {"PreToolUse": entries}}, indent=2) + "\n",
        encoding="utf-8",
    )
    return installed, config, tuple(candidates)


@pytest.mark.parametrize("case", CASES, ids=lambda item: item.provider)
def test_python_install_registers_direct_python_and_reclaims_shell_wrappers(
    case: Case,
) -> None:
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"python-hooks-{case.provider}-", dir=SCRATCH
    ) as td:
        project = Path(td)
        result = _install(case, project)
        assert result.returncode == 0, result.stdout + result.stderr
        config = project / case.config
        commands = _commands(config)
        assert commands
        assert all(".ps1" not in command.casefold() for command in commands)
        assert all(".sh" not in command.casefold() for command in commands)
        assert all(
            ".py" in command.casefold()
            or command.casefold().endswith(("python.exe", "python"))
            for command in commands
        )
        installed = project / case.installed_root
        source_wrappers = hook_installer.owned_hook_wrapper_sources(
            ROOT, case.provider
        )
        provider_root = ROOT / (
            "src.codex/skills/lead"
            if case.provider == "codex"
            else "src.claude/agents"
        )
        hook_shells = [
            installed / path.relative_to(provider_root) for path in source_wrappers
        ]
        assert all(not path.exists() for path in hook_shells)

        health = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/check-hook-health.py"),
                "--target",
                str(config),
                "--platform",
                case.provider,
                "--host-os",
                "windows" if os.name == "nt" else "posix",
                "--repo-root",
                str(ROOT),
                "--verify-fires",
            ],
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        assert health.returncode == 0, health.stdout + health.stderr


@pytest.mark.parametrize("case", CASES, ids=lambda item: item.provider)
def test_global_transaction_inventory_excludes_unrelated_provider_home(
    case: Case,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The global provider home is a boundary, never a snapshot root."""
    home = tmp_path / "home"
    target = home / f".{case.provider}"
    unrelated_directories = (
        target / "sessions",
        target / "vendor_imports",
    )
    for directory in unrelated_directories:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "large.bin").write_bytes(b"unrelated")

    source = ROOT / f"src.{case.provider}"
    if case.provider == "codex":
        agents_root = target
        docs_target = target / "AGENTS.md"
        source_tree = source / "skills"
        target_tree = target / "skills"
        mode_target = target / ".agents-mode.yaml"
        registration = target / "hooks.json"
    else:
        agents_root = target
        docs_target = target / "CLAUDE.md"
        source_tree = source
        target_tree = target
        mode_target = target / ".agents-mode.yaml"
        registration = target / "settings.json"

    paths = production_installer._installer_mutation_paths(
        provider=case.provider,
        source=source,
        target=target,
        agents_root=agents_root,
        docs_target=docs_target,
        source_tree=source_tree,
        target_tree=target_tree,
        mode_target=mode_target,
        registration=registration,
        shared_mode_target=home / ".agents-mode.yaml",
    )
    assert target not in paths
    assert all(
        path != directory
        and path not in directory.parents
        and directory not in path.parents
        for path in paths
        for directory in unrelated_directories
    )

    copied_directories: list[Path] = []
    original_copytree = production_installer.shutil.copytree

    def record_copytree(source_path, destination, *args, **kwargs):
        copied_directories.append(Path(source_path))
        return original_copytree(source_path, destination, *args, **kwargs)

    monkeypatch.setattr(production_installer.shutil, "copytree", record_copytree)
    with production_installer._InstallTransaction(paths, enabled=True) as transaction:
        transaction.commit()
    assert copied_directories == []


def test_transaction_restores_write_through_symlink_chain_referent(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external" / "settings.json"
    external.parent.mkdir()
    external.write_bytes(b'{"before": true}\n')
    intermediate = tmp_path / "links" / "intermediate.json"
    logical = tmp_path / "provider" / "settings.json"
    _make_file_symlink(intermediate, external)
    _make_file_symlink(logical, intermediate)
    logical_target = os.readlink(logical)
    intermediate_target = os.readlink(intermediate)

    with pytest.raises(RuntimeError, match="forced rollback"):
        with production_installer._InstallTransaction(
            [logical],
            enabled=True,
        ):
            external.write_bytes(b'{"after": true}\n')
            raise RuntimeError("forced rollback")

    assert logical.is_symlink()
    assert intermediate.is_symlink()
    assert os.readlink(logical) == logical_target
    assert os.readlink(intermediate) == intermediate_target
    assert external.read_bytes() == b'{"before": true}\n'


def test_transaction_restores_dangling_write_through_symlink_referent(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external" / "missing.json"
    external.parent.mkdir()
    logical = tmp_path / "provider" / "hooks.json"
    _make_file_symlink(logical, external)
    logical_target = os.readlink(logical)

    with pytest.raises(RuntimeError, match="forced rollback"):
        with production_installer._InstallTransaction(
            [logical],
            enabled=True,
        ):
            external.write_bytes(b'{"created": true}\n')
            raise RuntimeError("forced rollback")

    assert logical.is_symlink()
    assert os.readlink(logical) == logical_target
    assert not external.exists()


def test_transaction_commit_keeps_write_through_symlink_referent_change(
    tmp_path: Path,
) -> None:
    external = tmp_path / "external" / "hooks.json"
    external.parent.mkdir()
    external.write_bytes(b'{"before": true}\n')
    logical = tmp_path / "provider" / "hooks.json"
    _make_file_symlink(logical, external)
    logical_target = os.readlink(logical)

    with production_installer._InstallTransaction(
        [logical],
        enabled=True,
    ) as transaction:
        external.write_bytes(b'{"after": true}\n')
        transaction.commit()

    assert logical.is_symlink()
    assert os.readlink(logical) == logical_target
    assert external.read_bytes() == b'{"after": true}\n'


def test_transaction_rejects_symlink_cycle_before_mutation(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _make_file_symlink(first, second)
    _make_file_symlink(second, first)
    marker = tmp_path / "body-ran"

    with pytest.raises(ValueError, match="cycle"):
        with production_installer._InstallTransaction(
            [first],
            enabled=True,
        ):
            marker.write_text("unexpected", encoding="utf-8")

    assert not marker.exists()
    assert first.is_symlink()
    assert second.is_symlink()


def test_transaction_rejects_symlink_resolution_error_before_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    external = tmp_path / "external.json"
    external.write_bytes(b"before")
    logical = tmp_path / "hooks.json"
    _make_file_symlink(logical, external)
    marker = tmp_path / "body-ran"

    def fail_readlink(_path):
        raise OSError("forced readlink failure")

    monkeypatch.setattr(production_installer.os, "readlink", fail_readlink)
    with pytest.raises(ValueError, match="cannot read transaction symlink"):
        with production_installer._InstallTransaction(
            [logical],
            enabled=True,
        ):
            marker.write_text("unexpected", encoding="utf-8")

    assert not marker.exists()
    assert external.read_bytes() == b"before"


@pytest.mark.parametrize("case", CASES, ids=lambda item: item.provider)
def test_registration_symlink_referent_restored_after_reclaim_failure(
    case: Case,
) -> None:
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"registration-link-{case.provider}-", dir=SCRATCH
    ) as td:
        project = Path(td)
        registration = project / case.config
        external = project / "external" / f"{case.provider}-registration.json"
        external.parent.mkdir(parents=True)
        external.write_bytes(b'{"hooks": {}}\n')
        _make_file_symlink(registration, external)
        link_target = os.readlink(registration)
        before = _tree_snapshot(project)

        result = _install(case, project, "reclaim")
        output = result.stdout + result.stderr

        assert result.returncode != 0, output
        assert "abort" in output.casefold(), output
        assert "reclaim" in output.casefold(), output
        assert registration.is_symlink()
        assert os.readlink(registration) == link_target
        assert external.read_bytes() == b'{"hooks": {}}\n'
        assert _tree_snapshot(project) == before


@pytest.mark.parametrize("case", CASES, ids=lambda item: item.provider)
def test_successful_reinstall_preserves_owned_and_unrelated_state(case: Case) -> None:
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"python-idempotent-{case.provider}-", dir=SCRATCH
    ) as td:
        project = Path(td)
        baseline = _install(case, project)
        assert baseline.returncode == 0, baseline.stdout + baseline.stderr
        preserved = _seed_unrelated_provider_state(project, case)
        before = _tree_snapshot(project)

        result = _install(case, project)

        assert result.returncode == 0, result.stdout + result.stderr
        assert _tree_snapshot(project) == before
        assert all(path.exists() for path in preserved)


@pytest.mark.parametrize("case", CASES, ids=lambda item: item.provider)
@pytest.mark.parametrize("stage", ("sync", "register", "verify", "reclaim"))
def test_interruption_preserves_target_and_registration_bytes(
    case: Case, stage: str
) -> None:
    """An interrupted idempotent reinstall must leave its prior good state exact."""
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"python-abort-{case.provider}-{stage}-", dir=SCRATCH
    ) as td:
        project = Path(td)
        installed = project / case.installed_root
        config = project / case.config
        baseline = _install(case, project)
        assert baseline.returncode == 0, baseline.stdout + baseline.stderr
        preserved = _seed_unrelated_provider_state(project, case)
        before_project = _tree_snapshot(project)
        before_target = _tree_snapshot(installed)
        before_registration = config.read_bytes()

        interrupted = _install(case, project, stage)
        output = interrupted.stdout + interrupted.stderr
        assert interrupted.returncode != 0, output
        assert "abort" in output.casefold(), output
        assert config.read_bytes() == before_registration
        assert _tree_snapshot(installed) == before_target
        assert _tree_snapshot(project) == before_project
        assert all(path.exists() for path in preserved)


@pytest.mark.parametrize("case", CASES, ids=lambda item: item.provider)
def test_post_reclaim_failure_restores_owned_and_unrelated_state(
    case: Case,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure after retired-file reclaim restores the exact starting tree."""
    project = tmp_path / case.provider
    project.mkdir()
    preserved = _seed_unrelated_provider_state(project, case)
    payload = b"pack-owned retired powershell\n"
    relative = (
        "skills/lead/scripts/retired-owned.ps1"
        if case.provider == "codex"
        else "agents/scripts/retired-owned.ps1"
    )
    retired_root = (
        project / ".agents"
        if case.provider == "codex"
        else project / ".claude"
    )
    retired = retired_root / Path(relative)
    retired.parent.mkdir(parents=True, exist_ok=True)
    retired.write_bytes(payload)
    manifest_name = (
        "_CODEX_RETIRED_PS1"
        if case.provider == "codex"
        else "_CLAUDE_RETIRED_PS1"
    )
    monkeypatch.setattr(
        production_installer,
        manifest_name,
        {relative: hashlib.sha256(payload).hexdigest()},
    )

    def fail_after_reclaim(*_args, **_kwargs):
        raise RuntimeError("forced failure after retired-file reclaim")

    monkeypatch.setattr(production_installer, "_verify_files", fail_after_reclaim)
    before = _tree_snapshot(project)
    result = production_installer.install(
        case.provider,
        [
            "--target",
            str(project),
            "--force",
            "--allow-unsafe-target",
            "--no-hypothesis-hook",
        ],
    )

    assert result == 1
    assert _tree_snapshot(project) == before
    assert retired.read_bytes() == payload
    assert all(path.exists() for path in preserved)


def test_transaction_abort_absent_environment_is_exact_noop() -> None:
    result = _checkpoint(ROOT / ".scratch" / "absent" / "hooks.json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


def test_transaction_abort_invalid_stage_fails_loud_without_abort_marker() -> None:
    result = _checkpoint(
        ROOT / ".scratch" / "invalid" / "hooks.json",
        requested="not-a-stage",
    )
    output = result.stdout + result.stderr
    assert result.returncode not in (0, ABORT_EXIT)
    assert ABORT_ENV in output
    assert "TEST-ABORT:" not in output


def test_transaction_abort_rejects_unknown_scope() -> None:
    result = _checkpoint(
        ROOT / ".scratch" / "unknown-scope" / "hooks.json",
        requested="sync",
        install_scope="unknown",
    )
    output = result.stdout + result.stderr
    assert result.returncode not in (0, ABORT_EXIT)
    assert "invalid choice" in output
    assert "TEST-ABORT:" not in output


def test_transaction_abort_stage_mismatch_is_noop_for_valid_target() -> None:
    result = _checkpoint(
        ROOT / ".scratch" / "mismatch" / "hooks.json",
        stage="sync",
        requested="register",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TEST-ABORT:" not in result.stdout + result.stderr


@pytest.mark.parametrize("install_scope", ("repo", "target"))
def test_transaction_abort_accepts_only_explicit_non_global_scope(
    install_scope: str,
) -> None:
    result = _checkpoint(
        ROOT / ".scratch" / install_scope / "hooks.json",
        requested="sync",
        install_scope=install_scope,
    )
    output = result.stdout + result.stderr
    assert result.returncode == ABORT_EXIT, output
    assert "TEST-ABORT:" in output


def test_transaction_abort_rejects_global_scope_even_below_scratch() -> None:
    result = _checkpoint(
        ROOT / ".scratch" / "fake-global-home" / ".codex" / "hooks.json",
        requested="sync",
        install_scope="global",
    )
    output = result.stdout + result.stderr
    assert result.returncode not in (0, ABORT_EXIT)
    assert "forbidden for global install scope" in output
    assert "TEST-ABORT:" not in output


def test_transaction_abort_requires_pytest_provenance() -> None:
    result = _checkpoint(
        ROOT / ".scratch" / "provenance" / "hooks.json",
        requested="sync",
        pytest_provenance=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode not in (0, ABORT_EXIT)
    assert "requires pytest provenance" in output
    assert "TEST-ABORT:" not in output


@pytest.mark.parametrize(
    "target",
    (
        ROOT / ".scratch",
        ROOT / "not-scratch" / "hooks.json",
        ROOT / ".scratch" / ".." / "hooks.json",
    ),
    ids=("scratch-root", "outside-scratch", "traversal-escape"),
)
def test_transaction_abort_rejects_non_descendant_targets(target: Path) -> None:
    result = _checkpoint(target, requested="sync")
    output = result.stdout + result.stderr
    assert result.returncode not in (0, ABORT_EXIT)
    assert "repository .scratch" in output
    assert "TEST-ABORT:" not in output


def test_transaction_abort_rejects_symlink_escape() -> None:
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="abort-link-", dir=SCRATCH) as td:
        link = Path(td) / "escape"
        outside = ROOT / "outside-abort-link-target"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("directory symlink creation is unavailable")
        result = _checkpoint(link / "hooks.json", requested="sync")
    output = result.stdout + result.stderr
    assert result.returncode not in (0, ABORT_EXIT)
    assert "repository .scratch" in output
    assert "TEST-ABORT:" not in output


@pytest.mark.skipif(os.name != "nt", reason="Windows junction probe")
def test_transaction_abort_rejects_junction_escape() -> None:
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="abort-junction-", dir=SCRATCH) as td:
        junction = Path(td) / "escape"
        created = subprocess.run(
            [
                os.environ.get("COMSPEC", "cmd.exe"),
                "/c",
                "mklink",
                "/J",
                str(junction),
                str(ROOT),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if created.returncode != 0:
            pytest.skip("junction creation is unavailable")
        result = _checkpoint(junction / "hooks.json", requested="sync")
    output = result.stdout + result.stderr
    assert result.returncode not in (0, ABORT_EXIT)
    assert "repository .scratch" in output
    assert "TEST-ABORT:" not in output


@pytest.mark.parametrize("case", CASES, ids=lambda item: item.provider)
def test_reclaim_checkpoint_dominates_every_unlink(case: Case) -> None:
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f"reclaim-checkpoint-{case.provider}-", dir=SCRATCH
    ) as td:
        project = Path(td)
        installed, config, candidates = _seed_reclaim_fixture(project, case)
        before = _tree_snapshot(installed)
        env = os.environ.copy()
        env[ABORT_ENV] = "reclaim"
        env["PYTEST_CURRENT_TEST"] = "controlled-reclaim-checkpoint"
        result = subprocess.run(
            [
                sys.executable,
                str(HELPER_PATH),
                "--target",
                str(config),
                "--platform",
                case.provider,
                "--host-os",
                "windows" if os.name == "nt" else "posix",
                "--repo-root",
                str(ROOT),
                "--reclaim-root",
                str(installed),
                "--test-install-scope",
                "target",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        output = result.stdout + result.stderr
        assert result.returncode == ABORT_EXIT, output
        assert "TEST-ABORT:" in output
        assert _tree_snapshot(installed) == before
        assert all(path.is_file() for path in candidates)


def test_transaction_abort_policy_has_one_structural_owner() -> None:
    helper_source = HELPER_PATH.read_text(encoding="utf-8")
    assert _policy_owner_count(helper_source) == 1
    for path in (
        ROOT / "scripts/production_installer.py",
        ROOT / "scripts/install-codex.py",
        ROOT / "scripts/install-claude.py",
    ):
        assert _policy_owner_count(path.read_text(encoding="utf-8")) == 0


def test_transaction_abort_semantic_oracle_rejects_constructed_policy_owners() -> None:
    helper_source = HELPER_PATH.read_text(encoding="utf-8")
    planted = helper_source + "\nclass TestAbortPolicy:\n    pass\n"
    assert _policy_owner_count(planted) == 2


def test_transaction_abort_policy_owner_guard_rejects_installer_environment_reads() -> None:
    sources = {
        path: path.read_text(encoding="utf-8")
        for path in (
            ROOT / "scripts/production_installer.py",
            ROOT / "scripts/install-codex.py",
            ROOT / "scripts/install-claude.py",
        )
    }
    _assert_no_abort_env_reads(sources)
    planted_path = ROOT / "scripts/production_installer.py"
    planted = dict(sources)
    planted[planted_path] += f'\nos.environ.get("{ABORT_ENV}")\n'
    with pytest.raises(AssertionError):
        _assert_no_abort_env_reads(planted)


def test_transaction_abort_policy_owner_guard_rejects_second_stage_enumeration() -> None:
    sources = {
        path: path.read_text(encoding="utf-8")
        for path in (
            ROOT / "scripts/production_installer.py",
            ROOT / "scripts/install-codex.py",
            ROOT / "scripts/install-claude.py",
        )
    }
    _assert_no_second_stage_owner(sources)
    planted_path = ROOT / "scripts/install-codex.py"
    planted = dict(sources)
    planted[planted_path] += '\nSTAGES = ("sync", "register", "verify", "reclaim")\n'
    with pytest.raises(AssertionError):
        _assert_no_second_stage_owner(planted)


def test_transaction_abort_surface_is_hidden_from_operator_and_publication_paths() -> None:
    for path in (
        ROOT / "README.md",
        ROOT / "INSTALL.md",
        ROOT / "AGENTS.md",
        ROOT / "CLAUDE.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert ABORT_ENV not in text
        assert "--test-transaction-" not in text

    for script in (ROOT / "scripts/install-codex.py", ROOT / "scripts/install-claude.py"):
        completed = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert ABORT_ENV not in completed.stdout
        assert "--test-transaction-" not in completed.stdout
