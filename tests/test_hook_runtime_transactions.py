"""Python-installer transaction, confinement, and interruption tests."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections import Counter
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


def test_rmtree_callback_kwargs_keep_modern_onexc_contract() -> None:
    received: list[BaseException] = []

    def modern_rmtree(path, *, onexc):
        del path, onexc

    def handler(_function, _path, error):
        received.append(error)

    kwargs = production_installer._rmtree_callback_kwargs(modern_rmtree, handler)
    error = PermissionError("read-only entry")
    kwargs["onexc"](lambda _path: None, "entry", error)

    assert set(kwargs) == {"onexc"}
    assert received == [error]


def test_rmtree_callback_kwargs_adapt_legacy_exc_info() -> None:
    received: list[BaseException] = []

    def legacy_rmtree(path, *, onerror):
        del path, onerror

    def handler(_function, _path, error):
        received.append(error)

    kwargs = production_installer._rmtree_callback_kwargs(legacy_rmtree, handler)
    error = PermissionError("read-only entry")
    kwargs["onerror"](
        lambda _path: None,
        "entry",
        (PermissionError, error, None),
    )

    assert set(kwargs) == {"onerror"}
    assert received == [error]


def test_remove_readonly_tree_selects_legacy_callback_before_invocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tree = tmp_path / "tree"
    tree.mkdir()
    readonly = tree / "readonly.txt"
    readonly.write_text("payload", encoding="utf-8")
    readonly.chmod(stat.S_IREAD)
    speculative_mutation = tmp_path / "speculative-mutation"
    calls: list[set[str]] = []

    class LegacyRmtree:
        __signature__ = inspect.Signature(
            (
                inspect.Parameter("path", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                inspect.Parameter(
                    "onerror",
                    inspect.Parameter.KEYWORD_ONLY,
                    default=None,
                ),
            )
        )

        def __call__(self, path, **kwargs):
            calls.append(set(kwargs))
            if "onexc" in kwargs:
                speculative_mutation.write_text("called", encoding="utf-8")
                raise TypeError("unexpected onexc")
            assert Path(path) == tree
            error = PermissionError("read-only entry")

            def retry(value):
                Path(value).unlink()

            kwargs["onerror"](
                retry,
                str(readonly),
                (PermissionError, error, None),
            )

    monkeypatch.setattr(production_installer.shutil, "rmtree", LegacyRmtree())

    production_installer._remove_readonly_tree(tree)

    assert calls == [{"onerror"}]
    assert not speculative_mutation.exists()
    assert not readonly.exists()


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
    if case.provider == "codex":
        env["CODEX_BIN"] = str(ROOT / "tests/fixtures/fake_codex_hooks_host.py")
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
        project / ".agents" / "user-custom.txt"
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


def _make_directory_junction(link: Path, target: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows junction coverage")
    link.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "New-Item",
            "-ItemType",
            "Junction",
            "-Path",
            str(link),
            "-Target",
            str(target),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 or not os.path.isjunction(link):
        pytest.skip(f"junction creation is unavailable: {result.stdout}{result.stderr}")


ABORT_POLICY_PATHS = (
    HELPER_PATH,
    ROOT / "scripts/production_installer.py",
    ROOT / "scripts/install-codex.py",
    ROOT / "scripts/install-claude.py",
)
ABORT_STAGES = ("sync", "register", "verify", "reclaim")


def _abort_policy_sources() -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in ABORT_POLICY_PATHS}


def _fold_static_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _fold_static_string(node.left)
        right = _fold_static_string(node.right)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts = [_fold_static_string(value) for value in node.values]
        return "".join(parts) if all(part is not None for part in parts) else None
    return None


def _fold_stage_container(node: ast.AST | None) -> tuple[str, ...] | None:
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values = tuple(_fold_static_string(item) for item in node.elts)
    elif (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"tuple", "list", "set"}
        and len(node.args) == 1
        and not node.keywords
    ):
        return _fold_stage_container(node.args[0])
    else:
        return None
    if any(value is None for value in values):
        return None
    return tuple(value for value in values if value is not None)


def _assigned_name(node: ast.Assign | ast.AnnAssign) -> str:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    if len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return "<complex-target>"
    return targets[0].id


class AbortPolicyOwnershipContract:
    """Bounded AST owner proof for the test-only installer interruption policy."""

    _ENV_ALLOWLIST = frozenset(
        {
            ("scripts/install-hypothesis-hook.py", "TestAbortPolicy.resolve_and_preflight", "mapping", None),
            ("scripts/install-hypothesis-hook.py", "main", "get", "ORCHESTRARIUM_NO_HYPOTHESIS_HOOK"),
            ("scripts/production_installer.py", "_run", "copy", None),
            ("scripts/production_installer.py", "_run_hook_health_bounded", "copy", None),
            ("scripts/production_installer.py", "_install_hooks", "get", "CODEX_BIN"),
            ("scripts/production_installer.py", "_resolve_global_home", "get", "USERPROFILE"),
            ("scripts/production_installer.py", "_resolve_global_home", "get", "HOME"),
            ("scripts/production_installer.py", "install", "get", "ORCHESTRARIUM_NO_HYPOTHESIS_HOOK"),
        }
    )

    def __init__(self, sources: dict[Path, str]) -> None:
        self._sources = sources

    @staticmethod
    def _owner(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
        names: list[str] = []
        current = node
        while current in parents:
            current = parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(current.name)
        return ".".join(reversed(names)) or "<module>"

    @staticmethod
    def _relative(path: Path) -> str:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()

    def errors(self) -> tuple[str, ...]:
        errors: list[str] = []
        class_owners: list[tuple[str, str]] = []
        key_owners: list[tuple[str, str, str]] = []
        stage_owners: list[tuple[str, str, str]] = []
        environment_uses: list[tuple[str, str, str, str | None]] = []

        for path, source in self._sources.items():
            relative = self._relative(path)
            try:
                tree = ast.parse(source)
            except SyntaxError as exc:
                errors.append(f"ABORT-OWNER-PARSE:{relative}:{exc.lineno}")
                continue
            parents = {
                child: parent
                for parent in ast.walk(tree)
                for child in ast.iter_child_nodes(parent)
            }
            for node in ast.walk(tree):
                owner = self._owner(node, parents)
                if isinstance(node, ast.ClassDef) and node.name == "TestAbortPolicy":
                    class_owners.append((relative, node.name))
                if isinstance(node, (ast.Assign, ast.AnnAssign)):
                    value = node.value
                    name = _assigned_name(node)
                    if _fold_static_string(value) == ABORT_ENV:
                        key_owners.append((relative, owner, name))
                    stages = _fold_stage_container(value)
                    if stages is not None and len(stages) == 4 and set(stages) == set(ABORT_STAGES):
                        stage_owners.append((relative, owner, name))
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "os"
                    and any(alias.name in {"environ", "getenv"} for alias in node.names)
                ):
                    environment_uses.append((relative, owner, "import", None))
                if not (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "os"
                    and node.attr in {"environ", "getenv"}
                ):
                    continue
                if node.attr == "getenv":
                    call = parents.get(node)
                    key = (
                        _fold_static_string(call.args[0])
                        if isinstance(call, ast.Call) and call.args
                        else None
                    )
                    environment_uses.append((relative, owner, "getenv", key))
                    continue
                parent = parents.get(node)
                call = parents.get(parent) if parent is not None else None
                if (
                    isinstance(parent, ast.Attribute)
                    and parent.value is node
                    and parent.attr in {"get", "copy"}
                    and isinstance(call, ast.Call)
                ):
                    key = _fold_static_string(call.args[0]) if parent.attr == "get" and call.args else None
                    environment_uses.append((relative, owner, parent.attr, key))
                else:
                    environment_uses.append((relative, owner, "mapping", None))

        expected_class = [("scripts/install-hypothesis-hook.py", "TestAbortPolicy")]
        if class_owners != expected_class:
            errors.append(f"ABORT-OWNER-CLASS:{class_owners!r}")
        expected_key = [("scripts/install-hypothesis-hook.py", "TestAbortPolicy", "ABORT_ENV")]
        if key_owners != expected_key:
            errors.append(f"ABORT-OWNER-KEY:{key_owners!r}")
        expected_stages = [("scripts/install-hypothesis-hook.py", "TestAbortPolicy", "STAGES")]
        if stage_owners != expected_stages:
            errors.append(f"ABORT-OWNER-STAGES:{stage_owners!r}")
        for observation in environment_uses:
            if observation not in self._ENV_ALLOWLIST:
                errors.append(f"ABORT-OWNER-ENV:{observation!r}")
        actual_environment = Counter(environment_uses)
        expected_environment = Counter(self._ENV_ALLOWLIST)
        if actual_environment != expected_environment:
            errors.append(
                "ABORT-OWNER-ENV-CARDINALITY:"
                f"actual={sorted(actual_environment.items())!r}:"
                f"expected={sorted(expected_environment.items())!r}"
            )
        return tuple(sorted(set(errors)))

    def assert_valid(self) -> None:
        errors = self.errors()
        assert errors == (), "\n".join(errors)


def _run_fake_global_abort_case(case: Case, stage: str, tmp_path: Path) -> bool:
    fake_home = tmp_path / case.provider / stage / "home"
    config = fake_home / Path(case.config)
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('{"hooks": {}, "sentinel": "preserve"}\n', encoding="utf-8")
    if case.provider != "codex":
        installed = fake_home / Path(case.installed_root)
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "owned-sentinel.bin").write_bytes(b"owned-before")
    (fake_home / "unrelated-sentinel.bin").write_bytes(b"unrelated-before")
    before = _tree_snapshot(fake_home)
    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    env["USERPROFILE"] = str(fake_home)
    env[ABORT_ENV] = stage
    env.setdefault("PYTEST_CURRENT_TEST", f"fake-global-{case.provider}-{stage}")
    if case.provider == "codex":
        env["CODEX_BIN"] = str(ROOT / "tests/fixtures/fake_codex_hooks_host.py")
    result = subprocess.run(
        [sys.executable, str(case.script), "--global", "--force"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=240,
    )
    output = result.stdout + result.stderr
    assert result.returncode not in (0, ABORT_EXIT), (case.provider, stage, output)
    assert "forbidden for global install scope" in output, (case.provider, stage, output)
    assert "TEST-ABORT:" not in output, (case.provider, stage, output)
    assert _tree_snapshot(fake_home) == before, (case.provider, stage)
    return True


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


@pytest.mark.parametrize("case", CASES, ids=lambda item: item.provider)
def test_python_install_registers_direct_python_without_shell_hook_owners(
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


def test_global_codex_install_preserves_hooks_symlink_and_uses_real_sidecar(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    logical = home / ".codex" / "hooks.json"
    resolved = tmp_path / "shared" / "hooks.json"
    resolved.parent.mkdir()
    resolved.write_bytes(b'{"hooks": {}}\n')
    _make_file_symlink(logical, resolved)
    link_target = os.readlink(logical)
    env = os.environ.copy()
    env.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)
    env["CODEX_BIN"] = str(ROOT / "tests/fixtures/fake_codex_hooks_host.py")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/install-codex.py"),
            "--global",
            "--force",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=240,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert logical.is_symlink()
    assert os.readlink(logical) == link_target
    assert json.loads(resolved.read_text(encoding="utf-8"))["hooks"]
    inventory = resolved.parent / "codex-hook-inventory.json"
    assert inventory.is_file()
    assert not (logical.parent / inventory.name).exists()


def test_global_codex_install_resolves_hooks_referent_through_junction(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    logical = home / ".codex" / "hooks.json"
    real_root = tmp_path / "real-env"
    resolved = real_root / "Agents" / ".codex" / "hooks.json"
    resolved.parent.mkdir(parents=True)
    resolved.write_bytes(b'{"hooks": {}}\n')
    junction = tmp_path / "env"
    _make_directory_junction(junction, real_root)
    _make_file_symlink(
        logical,
        junction / "Agents" / ".codex" / "hooks.json",
    )
    file_link_target = os.readlink(logical)
    env = os.environ.copy()
    env.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)
    env["CODEX_BIN"] = str(ROOT / "tests/fixtures/fake_codex_hooks_host.py")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/install-codex.py"),
            "--global",
            "--force",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=240,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert logical.is_symlink()
    assert os.readlink(logical) == file_link_target
    assert os.path.isjunction(junction)
    inventory = resolved.parent / "codex-hook-inventory.json"
    assert inventory.is_file()
    assert not (logical.parent / inventory.name).exists()


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
        if case.provider == "codex":
            assert "hook transaction checkpoint failed at reclaim" in output, output
        else:
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


def test_transaction_abort_policy_contract_accepts_current_source() -> None:
    AbortPolicyOwnershipContract(_abort_policy_sources()).assert_valid()


def test_transaction_abort_policy_contract_rejects_archived_constructed_owner() -> None:
    assert "AbortPolicyOwnershipContract" in globals(), "ABORT-PROOF-MISSING"
    helper_source = HELPER_PATH.read_text(encoding="utf-8")
    mutant = helper_source + """

def duplicate_abort_owner():
    ambient = os.environ
    key = "ORCHESTRARIUM_TEST_" + "ABORT_HOOK_TRANSACTION_AFTER"
    stages = tuple(("sync", "register", "verify", "reclaim"))
    return ambient.get(key), stages
"""
    sources = _abort_policy_sources()
    sources[HELPER_PATH] = mutant
    errors = AbortPolicyOwnershipContract(sources).errors()
    assert any(error.startswith("ABORT-OWNER-ENV:") for error in errors), errors
    assert any(error.startswith("ABORT-OWNER-KEY:") for error in errors), errors
    assert any(error.startswith("ABORT-OWNER-STAGES:") for error in errors), errors


def test_transaction_abort_all_global_stages_preserve_state(tmp_path: Path) -> None:
    assert "_run_fake_global_abort_case" in globals(), "ABORT-GLOBAL-MATRIX-MISSING"
    observed = {
        (case.provider, stage)
        for case in CASES
        for stage in hook_installer.TEST_TRANSACTION_STAGES
        if _run_fake_global_abort_case(case, stage, tmp_path)
    }
    assert observed == {
        (provider, stage)
        for provider in ("codex", "claude")
        for stage in ("sync", "register", "verify", "reclaim")
    }


def test_transaction_abort_semantic_oracle_rejects_constructed_policy_owners() -> None:
    sources = _abort_policy_sources()
    sources[HELPER_PATH] += "\nclass TestAbortPolicy:\n    pass\n"
    errors = AbortPolicyOwnershipContract(sources).errors()
    assert any(error.startswith("ABORT-OWNER-CLASS:") for error in errors), errors


@pytest.mark.parametrize(
    "suffix",
    (
        f'\nos.environ.get("{ABORT_ENV}")\n',
        '\nos.getenv("ORCHESTRARIUM_TEST_" + "ABORT_HOOK_TRANSACTION_AFTER")\n',
        '\nfrom os import environ\n',
    ),
    ids=("direct-get", "split-getenv", "import-environ"),
)
def test_transaction_abort_policy_contract_rejects_installer_environment_reads(
    suffix: str,
) -> None:
    sources = _abort_policy_sources()
    planted_path = ROOT / "scripts/production_installer.py"
    sources[planted_path] += suffix
    errors = AbortPolicyOwnershipContract(sources).errors()
    assert any(error.startswith("ABORT-OWNER-ENV:") for error in errors), errors


def test_transaction_abort_policy_contract_rejects_duplicate_allowed_environment_read() -> None:
    sources = _abort_policy_sources()
    source = sources[HELPER_PATH]
    needle = "        source = os.environ if environ is None else environ\n"
    assert source.count(needle) == 1
    sources[HELPER_PATH] = source.replace(
        needle,
        needle + "        duplicate_ambient = os.environ\n",
        1,
    )
    errors = AbortPolicyOwnershipContract(sources).errors()
    assert any(
        error.startswith("ABORT-OWNER-ENV-CARDINALITY:") for error in errors
    ), errors


@pytest.mark.parametrize(
    "expression",
    (
        '("sync", "register", "verify", "reclaim")',
        '["sync", "register", "verify", "reclaim"]',
        '{"sync", "register", "verify", "reclaim"}',
        'tuple(("sync", "register", "verify", "reclaim"))',
    ),
    ids=("tuple", "list", "set", "constructed-tuple"),
)
def test_transaction_abort_policy_contract_rejects_second_stage_enumeration(
    expression: str,
) -> None:
    sources = _abort_policy_sources()
    planted_path = ROOT / "scripts/install-codex.py"
    sources[planted_path] += f"\nSTAGES = {expression}\n"
    errors = AbortPolicyOwnershipContract(sources).errors()
    assert any(error.startswith("ABORT-OWNER-STAGES:") for error in errors), errors


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


_VERIFY_FAILURE_IDS = (
    "E_INSTALL_VERIFY_FILES_MISSING",
    "E_INSTALL_VERIFY_RUNTIME_MISSING",
    "E_INSTALL_VERIFY_HOOK_RUNTIME_MISSING",
    "E_INSTALL_VERIFY_CONTROL_FILES_MISSING",
)


@pytest.mark.parametrize("stable_id", _VERIFY_FAILURE_IDS)
def test_rollback_identity_failure_settles_independent_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stable_id: str,
) -> None:
    """F6: one identity refusal cannot suppress disjoint cleanup or the cause."""

    project = tmp_path / stable_id.lower()
    project.mkdir()
    hooks = project / ".codex" / "hooks.json"
    inventory = project / ".codex" / "codex-hook-inventory.json"
    hooks.parent.mkdir()
    hooks_before = b'{"hooks": "before"}\n'
    inventory_before = b'{"inventory": "before"}\n'
    hooks.write_bytes(hooks_before)
    inventory.write_bytes(inventory_before)
    backup_paths: list[Path] = []
    real_mkdtemp = tempfile.mkdtemp

    def record_mkdtemp(suffix=None, prefix=None, dir=None):
        path = Path(real_mkdtemp(suffix=suffix, prefix=prefix, dir=tmp_path))
        backup_paths.append(path)
        return str(path)

    monkeypatch.setattr(production_installer.tempfile, "mkdtemp", record_mkdtemp)
    failure_type = getattr(production_installer, "_InstallFailure", None)
    original = (
        failure_type(stable_id, "verify", "forced")
        if isinstance(failure_type, type)
        else RuntimeError(stable_id)
    )
    bad = project / ".agents" / "bad.txt"
    good = project / ".agents" / "good.txt"

    with pytest.raises(BaseException) as caught:
        transaction = production_installer._InstallTransaction(
            [hooks, inventory], enabled=True
        )
        with transaction:
            owner = production_installer._CreateOnlyMutablePath(
                project, transaction, dry_run=False
            )
            owner.create_file(Path(".agents/bad.txt"), b"created bad\n")
            owner.create_file(Path(".agents/good.txt"), b"created good\n")
            bad.unlink()
            bad.write_bytes(b"replacement preserved\n")
            hooks.write_bytes(b"mutated hooks\n")
            inventory.write_bytes(b"mutated inventory\n")
            raise original

    aggregate = caught.value
    assert getattr(aggregate, "stable_id", None) == "E_ROLLBACK_SETTLEMENT_FAILED"
    assert getattr(aggregate, "cause", None) is original
    assert hooks.read_bytes() == hooks_before
    assert inventory.read_bytes() == inventory_before
    assert bad.read_bytes() == b"replacement preserved\n"
    assert not good.exists()
    member_ids = [member.stable_id for member in aggregate.members]
    assert member_ids
    assert set(member_ids) == {"E_ROLLBACK_CREATED_IDENTITY_CHANGED"}
    assert aggregate.recovery_path is None
    assert backup_paths and all(not path.exists() for path in backup_paths)


def test_rollback_restore_failure_retains_complete_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F6: a failed snapshot restore retains one reported recovery set."""

    target = tmp_path / "hooks.json"
    target.write_bytes(b"before\n")
    backup_paths: list[Path] = []
    real_mkdtemp = tempfile.mkdtemp

    def record_mkdtemp(suffix=None, prefix=None, dir=None):
        path = Path(real_mkdtemp(suffix=suffix, prefix=prefix, dir=tmp_path))
        backup_paths.append(path)
        return str(path)

    monkeypatch.setattr(production_installer.tempfile, "mkdtemp", record_mkdtemp)
    failure_type = getattr(production_installer, "_InstallFailure", None)
    original = (
        failure_type("E_INSTALL_VERIFY_FILES_MISSING", "verify", "forced")
        if isinstance(failure_type, type)
        else RuntimeError("E_INSTALL_VERIFY_FILES_MISSING")
    )
    if hasattr(production_installer._InstallTransaction, "_restore_entry"):
        monkeypatch.setattr(
            production_installer._InstallTransaction,
            "_restore_entry",
            lambda _self, _entry: (_ for _ in ()).throw(OSError("restore denied")),
        )
    else:
        monkeypatch.setattr(
            production_installer._InstallTransaction,
            "_restore",
            lambda _self: (_ for _ in ()).throw(OSError("restore denied")),
        )

    recovery_path: Path | None = None
    try:
        with pytest.raises(BaseException) as caught:
            transaction = production_installer._InstallTransaction(
                [target], enabled=True
            )
            with transaction:
                target.write_bytes(b"mutated\n")
                raise original
        aggregate = caught.value
        assert getattr(aggregate, "stable_id", None) == "E_ROLLBACK_SETTLEMENT_FAILED"
        assert getattr(aggregate, "cause", None) is original
        assert [member.stable_id for member in aggregate.members] == [
            "E_ROLLBACK_RESTORE_FAILED"
        ]
        recovery_path = aggregate.recovery_path
        assert recovery_path is not None and recovery_path.is_dir()
        assert recovery_path in backup_paths
    finally:
        if recovery_path is not None:
            shutil.rmtree(recovery_path, ignore_errors=True)


def test_install_transaction_excludes_dry_run_and_committed_success_from_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F6: disabled dry-run and committed success never enter rollback settlement."""

    dry_target = tmp_path / "dry.txt"
    dry_target.write_bytes(b"before\n")
    with production_installer._InstallTransaction([dry_target], enabled=False):
        dry_target.write_bytes(b"dry-run owner did not mutate this path\n")
    assert dry_target.read_bytes() == b"dry-run owner did not mutate this path\n"

    backup_paths: list[Path] = []
    real_mkdtemp = tempfile.mkdtemp

    def record_mkdtemp(suffix=None, prefix=None, dir=None):
        path = Path(real_mkdtemp(suffix=suffix, prefix=prefix, dir=tmp_path))
        backup_paths.append(path)
        return str(path)

    monkeypatch.setattr(production_installer.tempfile, "mkdtemp", record_mkdtemp)
    committed = tmp_path / "committed.txt"
    committed.write_bytes(b"before\n")
    transaction = production_installer._InstallTransaction(
        [committed], enabled=True
    )
    with transaction:
        committed.write_bytes(b"committed\n")
        transaction.commit()
    assert committed.read_bytes() == b"committed\n"
    assert backup_paths and all(not path.exists() for path in backup_paths)


def test_hook_health_deadline_failure_rolls_back_before_transaction_settles(
    tmp_path: Path,
) -> None:
    """A typed hook-health deadline restores the transaction's prior bytes."""

    target = tmp_path / "hooks.json"
    before = b'{"hooks":"before"}\n'
    target.write_bytes(before)

    with pytest.raises(production_installer._InstallFailure) as failure:
        transaction = production_installer._InstallTransaction(
            [target], enabled=True
        )
        with transaction:
            target.write_bytes(b'{"hooks":"mutated"}\n')
            raise production_installer._hook_health_failure(
                "hook health child deadline exceeded"
            )

    assert failure.value.stable_id == "E_HOOK_HEALTH_FAILED"
    assert failure.value.context == "health"
    assert "deadline" in str(failure.value.cause)
    assert target.read_bytes() == before


@pytest.mark.parametrize("stable_id", _VERIFY_FAILURE_IDS)
def test_every_precommit_verification_path_enters_rollback_with_typed_cause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stable_id: str,
) -> None:
    """F5/F6: no pre-commit validation branch returns from inside the transaction."""

    project = tmp_path / stable_id.lower()
    project.mkdir()
    observed: list[BaseException | None] = []
    original_exit = production_installer._InstallTransaction.__exit__

    def observe_exit(self, exc_type, exc, traceback):
        observed.append(exc)
        return original_exit(self, exc_type, exc, traceback)

    monkeypatch.setattr(
        production_installer._InstallTransaction, "__exit__", observe_exit
    )
    if stable_id == "E_INSTALL_VERIFY_FILES_MISSING":
        monkeypatch.setattr(
            production_installer, "_verify_files", lambda *_args, **_kwargs: ["missing"]
        )
        monkeypatch.setattr(
            production_installer, "_reclaim_retired", lambda *_args, **_kwargs: None
        )
    else:
        def remove_validation_target(*_args, **_kwargs):
            if stable_id == "E_INSTALL_VERIFY_RUNTIME_MISSING":
                path = (
                    project
                    / ".agents"
                    / "skills"
                    / "lead"
                    / "scripts"
                    / "agent-run-ledger.py"
                )
            elif stable_id == "E_INSTALL_VERIFY_HOOK_RUNTIME_MISSING":
                path = (
                    project
                    / ".agents"
                    / "skills"
                    / "lead"
                    / "scripts"
                    / "check-hook-health.py"
                )
            else:
                path = project / "AGENTS.md"
            path.unlink()

        monkeypatch.setattr(
            production_installer, "_reclaim_retired", remove_validation_target
        )

    result = production_installer.install(
        "codex",
        [
            "--target",
            str(project),
            "--force",
            "--allow-unsafe-target",
            "--no-hypothesis-hook",
        ],
    )

    assert result == 1
    assert len(observed) == 1
    assert getattr(observed[0], "stable_id", None) == stable_id
