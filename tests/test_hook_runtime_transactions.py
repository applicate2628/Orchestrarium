"""Real isolated wrapper -> Python -> wrapper installer transactions.

Normal and interruption transactions use only project targets below
``/.scratch/``. Four negative fixtures invoke global mode only after redirecting
the installer home into a unique scratch directory, and every case verifies
that the operator's live hook configuration metadata is unchanged.
"""

from __future__ import annotations

import ast
import importlib.util
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT / ".scratch"
HELPER_PATH = ROOT / "scripts" / "install-hypothesis-hook.py"
FORBIDDEN_DIRECT_TOKENS = ("powershell.exe", ".ps1", "/bin/bash", "bash.exe", ".sh")


def _load_helper():
    spec = importlib.util.spec_from_file_location(
        "install_hypothesis_hook_transactions", HELPER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HELPER = _load_helper()
ABORT_ENV = HELPER.TEST_TRANSACTION_ABORT_ENV
ABORT_STAGES = HELPER.TEST_TRANSACTION_STAGES
ABORT_EXIT = HELPER.TEST_TRANSACTION_ABORT_EXIT


@dataclass(frozen=True)
class InstallerCase:
    name: str
    platform: str
    script: Path
    shell: str
    target_dir: str
    config_file: str
    installed_root: str
    wrapper_count: int
    protected: tuple[str, ...]


CASES = (
    InstallerCase(
        "claude-powershell",
        "claude",
        ROOT / "scripts" / "install-claude.ps1",
        "powershell",
        ".claude",
        ".claude/settings.json",
        ".claude/agents",
        28,
        (
            "scripts/check-publication-safety.ps1",
            "scripts/await-codex-dispatch.ps1",
            "scripts/invoke-claude-api.ps1",
            "scripts/invoke-claude-prompt.ps1",
            "scripts/invoke-codex-prompt.ps1",
            "scripts/validate-skill-pack.ps1",
        ),
    ),
    InstallerCase(
        "claude-bash",
        "claude",
        ROOT / "scripts" / "install-claude.sh",
        "bash",
        ".claude",
        ".claude/settings.json",
        ".claude/agents",
        28,
        (
            "scripts/check-publication-safety.ps1",
            "scripts/await-codex-dispatch.ps1",
            "scripts/invoke-claude-api.ps1",
            "scripts/invoke-claude-prompt.ps1",
            "scripts/invoke-codex-prompt.ps1",
            "scripts/validate-skill-pack.ps1",
        ),
    ),
    InstallerCase(
        "codex-powershell",
        "codex",
        ROOT / "scripts" / "install-codex.ps1",
        "powershell",
        ".codex",
        ".codex/hooks.json",
        ".agents/skills/lead",
        26,
        (
            "scripts/check-publication-safety.ps1",
            "scripts/validate-skill-pack.ps1",
        ),
    ),
    InstallerCase(
        "codex-bash",
        "codex",
        ROOT / "scripts" / "install-codex.sh",
        "bash",
        ".codex",
        ".codex/hooks.json",
        ".agents/skills/lead",
        26,
        (
            "scripts/check-publication-safety.ps1",
            "scripts/validate-skill-pack.ps1",
        ),
    ),
)


def _live_config_metadata() -> dict[str, tuple[str, str | None]]:
    home = Path.home()
    paths = (
        home / ".codex" / "hooks.json",
        home / ".codex" / "config.toml",
        home / ".claude" / "settings.json",
    )
    result: dict[str, tuple[str, str | None]] = {}
    for path in paths:
        if path.is_file():
            result[str(path)] = (
                "present",
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        else:
            result[str(path)] = ("missing", None)
    return result


def _command(case: InstallerCase, target: Path, runtime: str) -> list[str]:
    if case.shell == "powershell":
        powershell = (
            shutil.which("pwsh.exe")
            or shutil.which("pwsh")
            or shutil.which("powershell.exe")
            or shutil.which("powershell")
        )
        if not powershell:
            pytest.skip("PowerShell is unavailable")
        return [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(case.script),
            "-Target",
            str(target),
            "-HookRuntime",
            runtime,
            "-Force",
            "-AllowUnsafeTarget",
        ]
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is unavailable")
    script_arg = str(case.script)
    target_arg = str(target)
    if os.name == "nt":
        cygpath_candidates = (
            Path(bash).with_name("cygpath.exe"),
            Path(bash).parent.parent / "usr" / "bin" / "cygpath.exe",
        )
        cygpath = next((path for path in cygpath_candidates if path.is_file()), None)
        if cygpath is None:
            pytest.skip("Git Bash cygpath.exe is unavailable")

        def as_posix(path: str) -> str:
            return subprocess.run(
                [str(cygpath), "-u", path],
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()

        script_arg = as_posix(script_arg)
        target_arg = as_posix(target_arg)
    return [
        bash,
        script_arg,
        "--target",
        target_arg,
        "--hook-runtime",
        runtime,
        "--force",
        "--allow-unsafe-target",
    ]


def _run_install(
    case: InstallerCase,
    project: Path,
    runtime: str,
    *,
    abort_after: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], float]:
    target = project / case.target_dir
    env = os.environ.copy()
    env.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
    env.pop(ABORT_ENV, None)
    if abort_after is not None:
        env[ABORT_ENV] = abort_after
    started = time.monotonic()
    completed = subprocess.run(
        _command(case, target, runtime),
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
    )
    return completed, time.monotonic() - started


def _run_health(
    case: InstallerCase, project: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "check-hook-health.py"),
            "--target",
            str(project / case.config_file),
            "--platform",
            case.platform,
            "--host-os",
            "windows" if os.name == "nt" else "posix",
            "--repo-root",
            str(ROOT),
            "--verify-fires",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _command_hooks(data: dict) -> list[dict]:
    result: list[dict] = []
    for entries in data["hooks"].values():
        for entry in entries:
            result.extend(entry.get("hooks", ()))
    return result


def _assert_registration_shape(
    case: InstallerCase, config: Path, runtime: str
) -> None:
    data = json.loads(config.read_text(encoding="utf-8"))
    hooks = _command_hooks(data)
    expected_stems = {
        path.stem for path in HELPER.owned_hook_wrapper_sources(ROOT, case.platform)
    }
    matching = [
        hook
        for hook in hooks
        if any(HELPER._hook_contains_marker(hook, stem) for stem in expected_stems)
    ]
    assert len(matching) == len(expected_stems)
    serialized = json.dumps(matching).lower()
    if runtime == "python":
        assert all(token not in serialized for token in FORBIDDEN_DIRECT_TOKENS)
        for hook in matching:
            if case.platform == "claude":
                assert Path(hook["command"]).is_absolute()
                assert len(hook["args"]) == 1
                target = Path(hook["args"][0])
            else:
                assert "args" not in hook
                executable, target_text = hook["command"].split(maxsplit=1)
                assert Path(executable).is_absolute()
                target = Path(target_text)
            assert target.is_absolute()
            assert target.suffix == ".py"
            assert target.is_file()
    else:
        assert all(
            HELPER._registration_wrapper_state(
                {"hooks": {"Probe": [{"hooks": [hook]}]}},
                {
                    stem
                    for stem in expected_stems
                    if HELPER._hook_contains_marker(hook, stem)
                },
            )
            for hook in matching
        )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_real_wrapper_python_wrapper_transaction(case: InstallerCase) -> None:
    SCRATCH.mkdir(exist_ok=True)
    live_before = _live_config_metadata()
    transaction_times: dict[str, float] = {}
    with tempfile.TemporaryDirectory(
        prefix=f"hook-runtime-{case.name}-", dir=SCRATCH
    ) as temp_dir:
        project = Path(temp_dir)
        installed_root = project / case.installed_root
        config = project / case.config_file

        wrapper_install, transaction_times["wrapper_before"] = _run_install(
            case, project, "wrapper"
        )
        assert wrapper_install.returncode == 0, (
            wrapper_install.stdout + wrapper_install.stderr
        )
        wrapper_registration = config.read_bytes()
        wrappers = HELPER.reclaimable_hook_wrappers(
            ROOT, installed_root, case.platform
        )
        assert len(wrappers) == case.wrapper_count
        assert all(path.is_file() for path in wrappers)
        assert all((installed_root / path).is_file() for path in case.protected)
        _assert_registration_shape(case, config, "wrapper")

        python_install, transaction_times["python"] = _run_install(
            case, project, "python"
        )
        assert python_install.returncode == 0, python_install.stdout + python_install.stderr
        assert (
            len(
                HELPER.reclaimable_hook_wrappers(
                    ROOT, installed_root, case.platform
                )
            )
            == 0
        )
        assert python_install.stdout.count("reclaimed hook wrapper:") == case.wrapper_count
        assert all((installed_root / path).is_file() for path in case.protected)
        _assert_registration_shape(case, config, "python")

        wrapper_restore, transaction_times["wrapper_after"] = _run_install(
            case, project, "wrapper"
        )
        assert wrapper_restore.returncode == 0, (
            wrapper_restore.stdout + wrapper_restore.stderr
        )
        restored = HELPER.reclaimable_hook_wrappers(
            ROOT, installed_root, case.platform
        )
        assert len(restored) == case.wrapper_count
        assert all(path.is_file() for path in restored)
        assert config.read_bytes() == wrapper_registration
        assert "reclaimed hook wrapper:" not in wrapper_restore.stdout
        assert all((installed_root / path).is_file() for path in case.protected)
        _assert_registration_shape(case, config, "wrapper")

    assert _live_config_metadata() == live_before
    print(
        json.dumps(
            {
                "case": case.name,
                "exit_codes": [0, 0, 0],
                "reclaim_count": case.wrapper_count,
                "seconds": {
                    key: round(value, 3) for key, value in transaction_times.items()
                },
                "live_configs_unchanged": True,
            },
            sort_keys=True,
        )
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_real_install_is_safe_when_interrupted(case: InstallerCase) -> None:
    SCRATCH.mkdir(exist_ok=True)
    live_before = _live_config_metadata()
    summaries: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(
        prefix=f"hook-runtime-abort-{case.name}-", dir=SCRATCH
    ) as temp_dir:
        transaction_root = Path(temp_dir)
        for stage in ABORT_STAGES:
            project = transaction_root / stage
            project.mkdir()
            installed_root = project / case.installed_root
            config = project / case.config_file

            wrapper_install, _ = _run_install(case, project, "wrapper")
            assert wrapper_install.returncode == 0, (
                wrapper_install.stdout + wrapper_install.stderr
            )
            wrapper_registration = config.read_bytes()
            wrappers_before = HELPER.reclaimable_hook_wrappers(
                ROOT, installed_root, case.platform
            )
            assert len(wrappers_before) == case.wrapper_count
            assert all(path.is_file() for path in wrappers_before)
            assert all((installed_root / path).is_file() for path in case.protected)
            _assert_registration_shape(case, config, "wrapper")

            interrupted, elapsed = _run_install(
                case, project, "python", abort_after=stage
            )
            interruption_output = interrupted.stdout + interrupted.stderr
            assert interrupted.returncode == ABORT_EXIT, interruption_output
            assert "TEST-ABORT:" in interruption_output
            assert f"after {stage.upper()}" in interruption_output

            wrappers_after = HELPER.reclaimable_hook_wrappers(
                ROOT, installed_root, case.platform
            )
            if stage == "sync":
                assert config.read_bytes() == wrapper_registration
                _assert_registration_shape(case, config, "wrapper")
                assert len(wrappers_after) == case.wrapper_count
            else:
                _assert_registration_shape(case, config, "python")
                # Every completed-stage abort happens before the next
                # mutation.  In particular, RECLAIM now checkpoints before
                # the first unlink, so the complete wrapper inventory must
                # remain on rejection.
                assert len(wrappers_after) == case.wrapper_count
            assert all(path.is_file() for path in wrappers_after)
            assert all((installed_root / path).is_file() for path in case.protected)

            health = _run_health(case, project)
            assert health.returncode == 0, health.stdout + health.stderr

            recovered, _ = _run_install(case, project, "python")
            assert recovered.returncode == 0, recovered.stdout + recovered.stderr
            assert (
                len(
                    HELPER.reclaimable_hook_wrappers(
                        ROOT, installed_root, case.platform
                    )
                )
                == 0
            )
            _assert_registration_shape(case, config, "python")
            assert all((installed_root / path).is_file() for path in case.protected)
            recovered_health = _run_health(case, project)
            assert recovered_health.returncode == 0, (
                recovered_health.stdout + recovered_health.stderr
            )
            summaries.append(
                {
                    "stage": stage,
                    "abort_exit": interrupted.returncode,
                    "wrappers_after_abort": len(wrappers_after),
                    "health_exit": health.returncode,
                    "recovery_exit": recovered.returncode,
                    "seconds_to_abort": round(elapsed, 3),
                }
            )

    assert _live_config_metadata() == live_before
    print(
        json.dumps(
            {
                "case": case.name,
                "stages": summaries,
                "live_configs_unchanged": True,
            },
            sort_keys=True,
        )
    )


def test_transaction_abort_seam_rejects_non_pytest_or_non_scratch_use(
    tmp_path: Path,
) -> None:
    checkpoint = [
        sys.executable,
        str(HELPER_PATH),
        "--target",
        str(tmp_path / "hooks.json"),
        "--platform",
        "codex",
        "--host-os",
        "windows" if os.name == "nt" else "posix",
        "--repo-root",
        str(ROOT),
        "--test-install-scope",
        "target",
        "--test-transaction-checkpoint",
        "sync",
    ]
    env = os.environ.copy()
    env[ABORT_ENV] = "sync"
    env.pop("PYTEST_CURRENT_TEST", None)
    without_pytest = subprocess.run(
        checkpoint,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert without_pytest.returncode != ABORT_EXIT
    assert "requires pytest provenance" in (
        without_pytest.stdout + without_pytest.stderr
    )

    env["PYTEST_CURRENT_TEST"] = "controlled-test-only-seam"
    outside_scratch = subprocess.run(
        checkpoint,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert outside_scratch.returncode != ABORT_EXIT
    assert "under repository .scratch" in (
        outside_scratch.stdout + outside_scratch.stderr
    )


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
        timeout=20,
    )


@dataclass(frozen=True)
class InstallerCheckpointContract:
    """Closed structural contract for the test-only interruption seam."""

    helper_text: str
    installer_texts: dict[Path, str]

    @staticmethod
    def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
        matches = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        assert len(matches) == 1, f"expected one function named {name}"
        return matches[0]

    @staticmethod
    def _assigned_name(node: ast.Assign | ast.AnnAssign) -> str | None:
        target = node.target if isinstance(node, ast.AnnAssign) else (
            node.targets[0] if len(node.targets) == 1 else None
        )
        return target.id if isinstance(target, ast.Name) else None

    @classmethod
    def _safe_constant(
        cls,
        node: ast.AST | None,
        names: dict[str, object] | None = None,
    ) -> object | None:
        """Fold only the closed constant grammar admitted by the R2 design.

        Mutated helper source is parsed, never imported or executed.  The
        grammar deliberately excludes attribute access, comprehensions, and
        arbitrary calls.
        """
        names = {} if names is None else names
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, int)):
            return node.value
        if isinstance(node, ast.Name):
            return names.get(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = cls._safe_constant(node.left, names)
            right = cls._safe_constant(node.right, names)
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            return None
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            values = [cls._safe_constant(element, names) for element in node.elts]
            if any(value is None for value in values):
                return None
            return tuple(values)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"tuple", "list", "set", "frozenset"}
            and len(node.args) == 1
            and not node.keywords
        ):
            value = cls._safe_constant(node.args[0], names)
            return tuple(value) if isinstance(value, tuple) else None
        return None

    @classmethod
    def _constant_bindings(cls, tree: ast.AST) -> dict[str, object]:
        bindings: dict[str, object] = {}
        assignments = [
            node
            for node in ast.walk(tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and cls._assigned_name(node) is not None
        ]
        for _ in range(len(assignments) + 1):
            changed = False
            for assignment in assignments:
                name = cls._assigned_name(assignment)
                assert name is not None
                value = cls._safe_constant(assignment.value, bindings)
                if value is not None and bindings.get(name) != value:
                    bindings[name] = value
                    changed = True
            if not changed:
                break
        return bindings

    @staticmethod
    def _enclosing_function(
        tree: ast.AST, target: ast.AST
    ) -> ast.FunctionDef | None:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and any(
                child is target for child in ast.walk(node)
            ):
                return node
        return None

    @staticmethod
    def _owner_path(tree: ast.AST, target: ast.AST) -> tuple[str, ...]:
        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        owners: list[str] = []
        current = target
        while current in parents:
            current = parents[current]
            if isinstance(current, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                owners.append(current.name)
        return tuple(reversed(owners))

    @staticmethod
    def _policy_class(tree: ast.Module) -> ast.ClassDef:
        matches = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "TestAbortPolicy"
        ]
        assert len(matches) == 1, "expected one TestAbortPolicy owner"
        return matches[0]

    @staticmethod
    def _method(owner: ast.ClassDef, name: str) -> ast.FunctionDef:
        matches = [
            node
            for node in owner.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        ]
        assert len(matches) == 1, f"expected one TestAbortPolicy.{name} method"
        return matches[0]

    @staticmethod
    def _extract_braced_function(
        text: str, declaration: str
    ) -> tuple[str, ...]:
        lines = text.splitlines()
        starts = [
            index
            for index, line in enumerate(lines)
            if line.strip() == declaration
        ]
        assert len(starts) == 1, f"expected one exact declaration: {declaration}"
        depth = 0
        result: list[str] = []
        for line in lines[starts[0] :]:
            stripped = line.strip()
            if stripped:
                result.append(stripped)
            depth += line.count("{") - line.count("}")
            if depth == 0:
                return tuple(result)
        raise AssertionError(f"unterminated function: {declaration}")

    def validate_helper(self) -> None:
        tree = ast.parse(self.helper_text)
        policy = self._policy_class(tree)
        resolver = self._method(policy, "resolve_and_preflight")
        checkpoint = self._method(policy, "checkpoint")
        reclaim = self._function(tree, "reclaim_stale_hook_wrappers")

        dataclass_decorators = [
            decorator
            for decorator in policy.decorator_list
            if isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Name)
            and decorator.func.id == "dataclass"
        ]
        assert len(dataclass_decorators) == 1, "TestAbortPolicy must be a dataclass"
        frozen = [
            keyword
            for keyword in dataclass_decorators[0].keywords
            if keyword.arg == "frozen"
        ]
        assert len(frozen) == 1
        assert isinstance(frozen[0].value, ast.Constant) and frozen[0].value.value is True

        bindings = self._constant_bindings(tree)
        policy_fact_violations: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.Return)):
                continue
            value = self._safe_constant(node.value, bindings)
            is_stage_set = (
                isinstance(value, tuple)
                and len(value) == len(ABORT_STAGES)
                and set(value) == set(ABORT_STAGES)
            )
            if value not in {
                ABORT_ENV,
                "PYTEST_CURRENT_TEST",
                "TEST-ABORT:",
                ABORT_EXIT,
            } and not is_stage_set:
                continue
            owner = self._owner_path(tree, node)
            if not owner or owner[0] != "TestAbortPolicy":
                name = (
                    self._assigned_name(node)
                    if isinstance(node, (ast.Assign, ast.AnnAssign))
                    else None
                )
                policy_fact_violations.append(
                    f"{name or '<expression>'}@{node.lineno}"
                )

        parents: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        environment_read_violations: list[str] = []
        for node in ast.walk(tree):
            direct_environ = (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr == "environ"
            )
            direct_getenv = (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr == "getenv"
            )
            if not (direct_environ or direct_getenv):
                continue
            owner = self._owner_path(tree, node)
            if not owner or owner[0] != "TestAbortPolicy":
                parent = parents.get(node)
                call = parents.get(parent) if isinstance(parent, ast.Attribute) else None
                allowed_opt_out_read = (
                    direct_environ
                    and isinstance(parent, ast.Attribute)
                    and parent.attr == "get"
                    and isinstance(call, ast.Call)
                    and call.func is parent
                    and len(call.args) >= 1
                    and isinstance(call.args[0], ast.Constant)
                    and call.args[0].value == "ORCHESTRARIUM_NO_HYPOTHESIS_HOOK"
                )
                if allowed_opt_out_read:
                    continue
                environment_read_violations.append(
                    f"{'.'.join(owner) or '<module>'}@{node.lineno}"
                )

        assert not policy_fact_violations, (
            "test-abort policy facts must be owned by TestAbortPolicy: "
            + ", ".join(policy_fact_violations)
        )
        assert not environment_read_violations, (
            "test-abort environment reads must be owned by TestAbortPolicy: "
            + ", ".join(environment_read_violations)
        )

        assert [arg.arg for arg in resolver.args.args] == [
            "cls",
            "environ",
            "install_scope",
            "target_path",
            "repo_root",
        ]
        assert [arg.arg for arg in checkpoint.args.args] == ["self", "stage"]
        assert [arg.arg for arg in reclaim.args.kwonlyargs] == [
            "repo_root",
            "installed_root",
            "platform",
            "registration_data",
            "dry_run",
            "abort_policy",
        ]

        global_scope_lines = [
            node.lineno
            for node in ast.walk(resolver)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "InstallScope"
            and node.attr == "GLOBAL"
        ]
        stage_policy_lines = [
            node.lineno
            for node in ast.walk(resolver)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id in {"cls", "TestAbortPolicy"}
            and node.attr == "STAGES"
        ]
        assert global_scope_lines and stage_policy_lines
        assert min(global_scope_lines) < min(stage_policy_lines), (
            "global scope rejection must dominate stage mismatch validation"
        )

        checkpoint_calls = [
            node
            for node in ast.walk(reclaim)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "abort_policy"
            and node.func.attr == "checkpoint"
        ]
        assert len(checkpoint_calls) == 1
        reclaim_call = checkpoint_calls[0]
        assert len(reclaim_call.args) == 1
        assert isinstance(reclaim_call.args[0], ast.Constant)
        assert reclaim_call.args[0].value == "reclaim"
        unlink_calls = [
            node
            for node in ast.walk(reclaim)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "unlink"
        ]
        assert unlink_calls
        assert all(reclaim_call.lineno < unlink.lineno for unlink in unlink_calls), (
            "RECLAIM checkpoint must dominate every unlink"
        )

    def validate_installers(self) -> None:
        expected = {
            ROOT / "scripts" / "install-claude.sh": (
                "bash",
                "settings_target",
                "claude",
                'if [[ ! -d "$TARGET" ]]; then',
            ),
            ROOT / "scripts" / "install-codex.sh": (
                "bash",
                "hooks_target",
                "codex",
                '# Create target parent directories as needed',
            ),
            ROOT / "scripts" / "install-claude.ps1": (
                "powershell",
                "SettingsTarget",
                "claude",
                'if (-not $DryRun -and -not (Test-Path -LiteralPath $TargetRoot)) {',
            ),
            ROOT / "scripts" / "install-codex.ps1": (
                "powershell",
                "HooksTarget",
                "codex",
                '# Create parent directories as needed',
            ),
        }
        assert set(self.installer_texts) == set(expected)
        for path, (shell, target, platform, first_mutation_anchor) in expected.items():
            text = self.installer_texts[path]
            if shell == "bash":
                preflight = self._extract_braced_function(
                    text, "run_test_hook_transaction_preflight() {"
                )
                assert preflight == (
                    "run_test_hook_transaction_preflight() {",
                    '"$python_cmd" "$hook_installer" \\',
                    f'--target "${target}" \\',
                    f"--platform {platform} \\",
                    '--repo-root "$REPO_DIR" \\',
                    '--test-install-scope "$MODE" \\',
                    "--test-transaction-preflight",
                    "}",
                )
                actual = self._extract_braced_function(
                    text, "run_test_hook_transaction_checkpoint() {"
                )
                assert actual == (
                    "run_test_hook_transaction_checkpoint() {",
                    'local stage="$1"',
                    '"$python_cmd" "$hook_installer" \\',
                    f'--target "${target}" \\',
                    f"--platform {platform} \\",
                    '--repo-root "$REPO_DIR" \\',
                    '--test-install-scope "$MODE" \\',
                    '--test-transaction-checkpoint "$stage"',
                    "}",
                )
                calls = re.findall(
                    r'^\s*run_test_hook_transaction_checkpoint\s+([^\s#]+)\s*$',
                    text,
                    flags=re.MULTILINE,
                )
                preflight_calls = re.findall(
                    r'^\s*run_test_hook_transaction_preflight\s*$',
                    text,
                    flags=re.MULTILINE,
                )
                preflight_call = re.search(
                    r'^\s*run_test_hook_transaction_preflight\s*$',
                    text,
                    flags=re.MULTILINE,
                )
            else:
                preflight = self._extract_braced_function(
                    text,
                    "function Invoke-TestHookTransactionPreflight {",
                )
                assert preflight == (
                    "function Invoke-TestHookTransactionPreflight {",
                    f"& $PythonCmd $HookInstaller --target ${target} "
                    f"--platform {platform} --repo-root $RepoDir "
                    "--test-install-scope $Mode --test-transaction-preflight",
                    "if ($LASTEXITCODE -ne 0) {",
                    '[Console]::Error.WriteLine("hook transaction test preflight '
                    'exited with code $LASTEXITCODE")',
                    "exit $LASTEXITCODE",
                    "}",
                    "}",
                )
                actual = self._extract_braced_function(
                    text,
                    "function Invoke-TestHookTransactionCheckpoint([string]$Stage) {",
                )
                assert actual == (
                    "function Invoke-TestHookTransactionCheckpoint([string]$Stage) {",
                    f"& $PythonCmd $HookInstaller --target ${target} "
                    f"--platform {platform} --repo-root $RepoDir "
                    "--test-install-scope $Mode "
                    "--test-transaction-checkpoint $Stage",
                    "if ($LASTEXITCODE -ne 0) {",
                    '[Console]::Error.WriteLine("hook transaction test checkpoint '
                    'exited with code $LASTEXITCODE")',
                    "exit $LASTEXITCODE",
                    "}",
                    "}",
                )
                calls = re.findall(
                    r'^\s*Invoke-TestHookTransactionCheckpoint\s+"([^"]+)"\s*$',
                    text,
                    flags=re.MULTILINE,
                )
                preflight_calls = re.findall(
                    r'^\s*Invoke-TestHookTransactionPreflight\s*$',
                    text,
                    flags=re.MULTILINE,
                )
                preflight_call = re.search(
                    r'^\s*Invoke-TestHookTransactionPreflight\s*$',
                    text,
                    flags=re.MULTILINE,
                )
            assert tuple(calls) == ("sync", "register", "verify")
            assert len(preflight_calls) == 1
            assert preflight_call is not None
            mutation_position = text.index(first_mutation_anchor)
            assert preflight_call.start() < mutation_position, (
                f"{path.name} must preflight before its first mutable SYNC operation"
            )
            assert text.count("--test-transaction-preflight") == 1

    def validate(self) -> None:
        self.validate_helper()
        self.validate_installers()


def _checkpoint_contract(
    *,
    helper_text: str | None = None,
    installer_texts: dict[Path, str] | None = None,
) -> InstallerCheckpointContract:
    return InstallerCheckpointContract(
        helper_text=(
            HELPER_PATH.read_text(encoding="utf-8")
            if helper_text is None
            else helper_text
        ),
        installer_texts=(
            {
                case.script: case.script.read_text(encoding="utf-8")
                for case in CASES
            }
            if installer_texts is None
            else installer_texts
        ),
    )


def test_transaction_abort_policy_has_one_structural_owner() -> None:
    _checkpoint_contract().validate()


@pytest.mark.parametrize(
    ("name", "injected"),
    (
        (
            "split-abort-key",
            "\ndef shadow_split_key_parser():\n"
            '    key = "ORCHESTRARIUM_" + "TEST_ABORT_HOOK_TRANSACTION_AFTER"\n'
            "    return os.environ.get(key)\n",
        ),
        (
            "environment-alias-get",
            "\ndef shadow_environment_alias():\n"
            "    ambient = os.environ\n"
            "    return ambient.get(TestAbortPolicy.ABORT_ENV)\n",
        ),
        (
            "constructor-built-stages",
            "\ndef shadow_stage_collection():\n"
            '    return tuple(["sync", "register", "verify", "reclaim"])\n',
        ),
        (
            "arbitrarily-named-second-parser",
            "\ndef collect_optional_transaction_mode():\n"
            "    return os.getenv(TestAbortPolicy.ABORT_ENV)\n",
        ),
        (
            "moved-marker-and-exit-facts",
            '\nSHADOW_ABORT_MARKER = "TEST-" + "ABORT:"\n'
            "SHADOW_ABORT_EXIT = 86\n",
        ),
    ),
    ids=(
        "split-abort-key",
        "environment-alias-get",
        "constructor-built-stages",
        "arbitrarily-named-second-parser",
        "moved-marker-and-exit-facts",
    ),
)
def test_transaction_abort_semantic_oracle_rejects_constructed_policy_owners(
    name: str,
    injected: str,
) -> None:
    # First pin the real helper to the intended owner.  On the pre-fix source
    # this is the intentional RED for every semantic row; after the owner lands,
    # each appended mutant must fail with the same ownership diagnostic.
    _checkpoint_contract().validate_helper()
    mutation = HELPER_PATH.read_text(encoding="utf-8") + injected
    with pytest.raises(
        AssertionError,
        match=r"(policy facts|environment reads).*TestAbortPolicy",
    ):
        _checkpoint_contract(helper_text=mutation).validate_helper()


@pytest.mark.parametrize(
    ("relative_path", "injected"),
    (
        (
            "scripts/install-codex.sh",
            '  printenv "ORCHESTRARIUM_TEST_ABORT_HOOK_TRANSACTION_AFTER"\n',
        ),
        (
            "scripts/install-claude.sh",
            '  local abort_name="ORCHESTRARIUM_"\n'
            '  abort_name+="TEST_ABORT_HOOK_TRANSACTION_AFTER"\n'
            '  printf "%s" "${!abort_name}"\n',
        ),
        (
            "scripts/install-codex.ps1",
            "            Get-Item Env:ORCHESTRARIUM_TEST_ABORT_HOOK_TRANSACTION_AFTER\n",
        ),
        (
            "scripts/install-claude.ps1",
            '            [Environment]::GetEnvironmentVariable('
            '"ORCHESTRARIUM_" + "TEST_ABORT_HOOK_TRANSACTION_AFTER")\n',
        ),
    ),
    ids=("bash-direct", "bash-indirect", "powershell-direct", "powershell-split"),
)
def test_transaction_abort_policy_owner_guard_rejects_installer_environment_reads(
    relative_path: str,
    injected: str,
) -> None:
    path = ROOT / relative_path
    texts = {
        case.script: case.script.read_text(encoding="utf-8") for case in CASES
    }
    declaration = (
        "run_test_hook_transaction_checkpoint() {\n"
        if path.suffix == ".sh"
        else "function Invoke-TestHookTransactionCheckpoint([string]$Stage) {\n"
    )
    texts[path] = texts[path].replace(declaration, declaration + injected, 1)
    with pytest.raises(AssertionError):
        _checkpoint_contract(installer_texts=texts).validate()


def test_transaction_abort_policy_owner_guard_rejects_second_stage_enumeration() -> None:
    mutation = HELPER_PATH.read_text(encoding="utf-8").replace(
        "TEST_TRANSACTION_STAGES = TestAbortPolicy.STAGES",
        "TEST_TRANSACTION_STAGES = TestAbortPolicy.STAGES\n"
        'SECOND_STAGE_OWNER = ("sync", "register", "verify", "reclaim")',
        1,
    )
    assert mutation != HELPER_PATH.read_text(encoding="utf-8")
    with pytest.raises(AssertionError):
        _checkpoint_contract(helper_text=mutation).validate()


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


def test_transaction_abort_stage_mismatch_is_noop_for_valid_scratch_target() -> None:
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
    with tempfile.TemporaryDirectory(prefix="abort-link-", dir=SCRATCH) as temp_dir:
        link = Path(temp_dir) / "escape"
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
    with tempfile.TemporaryDirectory(prefix="abort-junction-", dir=SCRATCH) as temp_dir:
        junction = Path(temp_dir) / "escape"
        created = subprocess.run(
            [os.environ.get("COMSPEC", "cmd.exe"), "/c", "mklink", "/J", str(junction), str(ROOT)],
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


def _tracked_hidden_control_surfaces() -> dict[Path, frozenset[str]]:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.split(b"\0")
    surfaces: dict[Path, frozenset[str]] = {}
    for raw in tracked:
        if not raw:
            continue
        relative = Path(os.fsdecode(raw))
        posix = relative.as_posix()
        lower = posix.lower()
        basename = relative.name.lower()
        categories: set[str] = set()
        if (
            (
                relative.suffix.lower() == ".md"
                and (
                    basename.startswith(("readme", "install"))
                    or "agents" in basename
                    or "help" in basename
                )
            )
            or "/templates/" in f"/{lower}/"
        ):
            categories.add("operator")
        if (
            lower.startswith("docs/")
            or lower.startswith("shared/references/")
            or lower.startswith("references-")
        ):
            categories.add("documentation")
        if (
            basename == "release_notes.md"
            or basename.startswith(("changelog", "history"))
            or (
                lower.startswith("scripts/")
                and "release" in basename
            )
        ):
            categories.add("release")
        if (
            "publication" in basename
            or "publish" in basename
            or "release" in basename
        ):
            categories.add("publication")
        if categories:
            surfaces[ROOT / relative] = frozenset(categories)
    return surfaces


def test_transaction_abort_surface_is_hidden_from_operator_and_publication_paths() -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    help_result = subprocess.run(
        [sys.executable, str(HELPER_PATH), "--help"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert help_result.returncode == 0
    assert "--test-transaction-checkpoint" not in help_result.stdout
    assert "--test-install-scope" not in help_result.stdout

    surfaces = _tracked_hidden_control_surfaces()
    assert set().union(*surfaces.values()) == {
        "operator",
        "documentation",
        "release",
        "publication",
    }
    hidden_tokens = (
        ABORT_ENV,
        "--test-transaction-checkpoint",
        "--test-install-scope",
        "TEST-ABORT",
    )
    hits: list[str] = []
    for path, categories in surfaces.items():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for token in hidden_tokens:
            if token in text:
                hits.append(
                    f"{','.join(sorted(categories))}:"
                    f"{path.relative_to(ROOT)}:{token}"
                )
    assert hits == []


def _global_command(
    case: InstallerCase,
    fake_home: Path,
    *,
    hook_runtime: str,
    requested_stage: str | None,
) -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    env.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
    env.pop(ABORT_ENV, None)
    env.pop("PYTEST_CURRENT_TEST", None)
    if requested_stage is not None:
        env[ABORT_ENV] = requested_stage
        env["PYTEST_CURRENT_TEST"] = "controlled-global-rejection-fixture"
    env["USERPROFILE"] = str(fake_home)
    env["HOME"] = str(fake_home)
    if case.shell == "powershell":
        powershell = (
            shutil.which("pwsh.exe")
            or shutil.which("pwsh")
            or shutil.which("powershell.exe")
            or shutil.which("powershell")
        )
        if not powershell:
            pytest.skip("PowerShell is unavailable")
        return (
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(case.script),
                "-Global",
                "-HookRuntime",
                hook_runtime,
                "-Force",
            ],
            env,
        )

    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is unavailable")
    script_arg = str(case.script)
    if os.name == "nt":
        bash_path = Path(bash)
        cygpath_candidates = (
            bash_path.with_name("cygpath.exe"),
            bash_path.parent.parent / "usr" / "bin" / "cygpath.exe",
        )
        cygpath = next(
            (candidate for candidate in cygpath_candidates if candidate.is_file()),
            None,
        )
        if cygpath is None:
            pytest.skip("Git Bash cygpath.exe is unavailable")

        def as_posix(path: Path) -> str:
            return subprocess.run(
                [str(cygpath), "-u", str(path)],
                capture_output=True,
                check=True,
                text=True,
            ).stdout.strip()

        script_arg = as_posix(case.script)
        env["HOME"] = as_posix(fake_home)
    return (
        [
            bash,
            script_arg,
            "--global",
            "--hook-runtime",
            hook_runtime,
            "--force",
        ],
        env,
    )


def _tree_snapshot(
    root: Path,
    *,
    excluded: frozenset[str] = frozenset(),
) -> tuple[tuple[str, str, str], ...]:
    entries: list[tuple[str, str, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
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


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
@pytest.mark.parametrize("requested_stage", ABORT_STAGES)
def test_real_global_installer_rejects_abort_request_at_every_stage_before_mutation(
    case: InstallerCase,
    requested_stage: str,
) -> None:
    SCRATCH.mkdir(exist_ok=True)
    live_before = _live_config_metadata()
    with tempfile.TemporaryDirectory(
        prefix=f"global-abort-reject-{case.name}-", dir=SCRATCH
    ) as temp_dir:
        fake_home = Path(temp_dir).resolve()
        runtime_noise = frozenset(
            {"AppData/Local/Microsoft/PowerShell/StartupProfileData-NonInteractive"}
            if case.shell == "powershell"
            else ()
        )
        config = fake_home / case.config_file
        config.parent.mkdir(parents=True)
        config.write_text(
            '{"sentinel":"global-scope-must-not-register"}\n',
            encoding="utf-8",
        )
        baseline_command, baseline_env = _global_command(
            case,
            fake_home,
            hook_runtime="wrapper",
            requested_stage=None,
        )
        baseline = subprocess.run(
            baseline_command,
            cwd=ROOT,
            env=baseline_env,
            capture_output=True,
            text=True,
            timeout=240,
        )
        assert baseline.returncode == 0, baseline.stdout + baseline.stderr

        installed_root = fake_home / (
            ".claude/agents"
            if case.platform == "claude"
            else ".codex/skills/lead"
        )
        scope_sentinel = fake_home / "scope-preflight-sentinel.txt"
        target_sentinel = installed_root / "target-preflight-sentinel.txt"
        scope_sentinel.write_text("scope sentinel\n", encoding="utf-8")
        target_sentinel.write_text("target sentinel\n", encoding="utf-8")
        wrappers_before = tuple(
            path.relative_to(installed_root).as_posix()
            for path in HELPER.reclaimable_hook_wrappers(
                ROOT, installed_root, case.platform
            )
        )
        assert len(wrappers_before) == case.wrapper_count
        before_config = config.read_bytes()
        if runtime_noise:
            assert runtime_noise == frozenset(
                {"AppData/Local/Microsoft/PowerShell/StartupProfileData-NonInteractive"}
            )
            assert (fake_home / next(iter(runtime_noise))).is_file()
        before_tree = _tree_snapshot(fake_home, excluded=runtime_noise)
        before_sentinels = (
            scope_sentinel.read_bytes(),
            target_sentinel.read_bytes(),
        )

        command, env = _global_command(
            case,
            fake_home,
            hook_runtime="python",
            requested_stage=requested_stage,
        )
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
        )
        output = completed.stdout + completed.stderr
        wrappers_after = tuple(
            path.relative_to(installed_root).as_posix()
            for path in HELPER.reclaimable_hook_wrappers(
                ROOT, installed_root, case.platform
            )
        )
        after_sentinels = (
            scope_sentinel.read_bytes() if scope_sentinel.is_file() else None,
            target_sentinel.read_bytes() if target_sentinel.is_file() else None,
        )

        assert completed.returncode not in (0, ABORT_EXIT), output
        assert "forbidden for global install scope" in output
        assert "TEST-ABORT:" not in output
        assert config.is_file()
        assert config.read_bytes() == before_config
        if runtime_noise:
            assert (fake_home / next(iter(runtime_noise))).is_file()
        assert _tree_snapshot(fake_home, excluded=runtime_noise) == before_tree
        assert wrappers_after == wrappers_before
        assert after_sentinels == before_sentinels
        assert config.resolve().is_relative_to(fake_home)
        normalized_output = output.replace("\\", "/").lower()
        for live_config in _live_config_metadata():
            assert Path(live_config).resolve().as_posix().lower() not in normalized_output

    assert _live_config_metadata() == live_before


def test_reclaim_checkpoint_dominates_every_unlink() -> None:
    case = next(case for case in CASES if case.name == "codex-bash")
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="reclaim-checkpoint-dominance-", dir=SCRATCH
    ) as temp_dir:
        project = Path(temp_dir)
        installed_root = project / case.installed_root
        config = project / case.config_file

        wrapper_install, _ = _run_install(case, project, "wrapper")
        assert wrapper_install.returncode == 0, (
            wrapper_install.stdout + wrapper_install.stderr
        )
        interrupted, _ = _run_install(
            case,
            project,
            "python",
            abort_after="verify",
        )
        assert interrupted.returncode == ABORT_EXIT, (
            interrupted.stdout + interrupted.stderr
        )
        wrappers_before = tuple(
            path.relative_to(installed_root).as_posix()
            for path in HELPER.reclaimable_hook_wrappers(
                ROOT, installed_root, case.platform
            )
        )
        assert len(wrappers_before) == case.wrapper_count

        env = os.environ.copy()
        env[ABORT_ENV] = "reclaim"
        env["PYTEST_CURRENT_TEST"] = "controlled-direct-reclaim-fixture"
        rejected = subprocess.run(
            [
                sys.executable,
                str(HELPER_PATH),
                "--target",
                str(config),
                "--platform",
                case.platform,
                "--host-os",
                "windows" if os.name == "nt" else "posix",
                "--repo-root",
                str(ROOT),
                "--reclaim-root",
                str(installed_root),
                "--test-install-scope",
                "global",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = rejected.stdout + rejected.stderr
        wrappers_after = tuple(
            path.relative_to(installed_root).as_posix()
            for path in HELPER.reclaimable_hook_wrappers(
                ROOT, installed_root, case.platform
            )
        )
        assert rejected.returncode not in (0, ABORT_EXIT), output
        assert "forbidden for global install scope" in output
        assert "TEST-ABORT:" not in output
        assert wrappers_after == wrappers_before, (
            "RECLAIM rejected after unlink; complete wrapper inventory was not preserved"
        )

    _checkpoint_contract().validate_helper()
