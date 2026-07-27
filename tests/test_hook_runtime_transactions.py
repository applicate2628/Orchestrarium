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
        cygpath = Path(bash).with_name("cygpath.exe")
        if not cygpath.is_file():
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
                expected_wrapper_count = (
                    case.wrapper_count - 1
                    if stage == "reclaim"
                    else case.wrapper_count
                )
                assert len(wrappers_after) == expected_wrapper_count
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

    @staticmethod
    def _literal_stage_sequence(node: ast.AST | None) -> tuple[str, ...] | None:
        if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            return None
        values: list[str] = []
        for element in node.elts:
            if not isinstance(element, ast.Constant) or not isinstance(
                element.value, str
            ):
                return None
            values.append(element.value)
        return tuple(values)

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
        stage_assignments: list[tuple[str | None, tuple[str, ...]]] = []
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            sequence = self._literal_stage_sequence(value)
            if sequence is not None and set(sequence) == set(ABORT_STAGES):
                stage_assignments.append((self._assigned_name(node), sequence))
        assert stage_assignments == [
            ("TEST_TRANSACTION_STAGES", ("sync", "register", "verify", "reclaim"))
        ]

        resolver = self._function(tree, "resolve_test_abort_request")
        checkpoint = self._function(tree, "test_transaction_checkpoint")
        reclaim = self._function(tree, "reclaim_stale_hook_wrappers")

        resolver_environment_reads = [
            node
            for node in ast.walk(resolver)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr == "environ"
        ]
        assert len(resolver_environment_reads) == 1
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "os"
            and node.func.attr == "getenv"
            for node in ast.walk(resolver)
        )

        policy_token_loads = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == "TEST_TRANSACTION_ABORT_ENV"
        ]
        assert policy_token_loads
        assert {
            self._enclosing_function(tree, node).name
            for node in policy_token_loads
            if self._enclosing_function(tree, node) is not None
        } == {"resolve_test_abort_request"}

        assert [arg.arg for arg in checkpoint.args.args] == [
            "stage",
            "target_path",
            "repo_root",
            "abort_request",
            "install_scope",
        ]
        assert [arg.arg for arg in reclaim.args.kwonlyargs] == [
            "repo_root",
            "installed_root",
            "platform",
            "registration_data",
            "dry_run",
            "install_scope",
            "abort_request",
        ]
        for owner in (checkpoint, reclaim):
            assert not any(
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr in {"environ", "getenv"}
                for node in ast.walk(owner)
            )
            assert not any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"get", "getenv"}
                for node in ast.walk(owner)
            )
            assert not any(
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and "env" in node.value.id.lower()
                for node in ast.walk(owner)
            )

        assert self.helper_text.count(
            'TEST_TRANSACTION_ABORT_ENV = "'
        ) == 1
        assert self.helper_text.count('"PYTEST_CURRENT_TEST"') == 1
        assert self.helper_text.count('"TEST-ABORT:') == 1
        exit_loads = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id == "TEST_TRANSACTION_ABORT_EXIT"
        ]
        assert len(exit_loads) == 1

        checkpoint_calls = [
            node
            for node in ast.walk(reclaim)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "test_transaction_checkpoint"
        ]
        assert len(checkpoint_calls) == 1
        reclaim_call = checkpoint_calls[0]
        assert len(reclaim_call.args) == 5
        assert isinstance(reclaim_call.args[0], ast.Constant)
        assert reclaim_call.args[0].value == "reclaim"
        assert isinstance(reclaim_call.args[3], ast.Name)
        assert reclaim_call.args[3].id == "abort_request"
        assert isinstance(reclaim_call.args[4], ast.Name)
        assert reclaim_call.args[4].id == "install_scope"

    def validate_installers(self) -> None:
        expected = {
            ROOT / "scripts" / "install-claude.sh": (
                "bash",
                "settings_target",
                "claude",
            ),
            ROOT / "scripts" / "install-codex.sh": (
                "bash",
                "hooks_target",
                "codex",
            ),
            ROOT / "scripts" / "install-claude.ps1": (
                "powershell",
                "SettingsTarget",
                "claude",
            ),
            ROOT / "scripts" / "install-codex.ps1": (
                "powershell",
                "HooksTarget",
                "codex",
            ),
        }
        assert set(self.installer_texts) == set(expected)
        for path, (shell, target, platform) in expected.items():
            text = self.installer_texts[path]
            if shell == "bash":
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
            else:
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
            assert tuple(calls) == ("sync", "register", "verify")

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
        'TEST_TRANSACTION_STAGES = ("sync", "register", "verify", "reclaim")',
        'TEST_TRANSACTION_STAGES = ("sync", "register", "verify", "reclaim")\n'
        'SECOND_STAGE_OWNER = ("sync", "register", "verify", "reclaim")',
        1,
    )
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
) -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    env.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
    env[ABORT_ENV] = "sync"
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
                "python",
                "-Force",
            ],
            env,
        )

    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is unavailable")
    script_arg = str(case.script)
    if os.name == "nt":
        cygpath = Path(bash).with_name("cygpath.exe")
        if not cygpath.is_file():
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
            "python",
            "--force",
        ],
        env,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_real_global_installer_rejects_abort_request_in_isolated_fake_home(
    case: InstallerCase,
) -> None:
    SCRATCH.mkdir(exist_ok=True)
    live_before = _live_config_metadata()
    with tempfile.TemporaryDirectory(
        prefix=f"global-abort-reject-{case.name}-", dir=SCRATCH
    ) as temp_dir:
        fake_home = Path(temp_dir).resolve()
        config = fake_home / case.config_file
        config.parent.mkdir(parents=True)
        config.write_text(
            '{"sentinel":"global-scope-must-not-register"}\n',
            encoding="utf-8",
        )
        before = (
            config.is_file(),
            hashlib.sha256(config.read_bytes()).hexdigest(),
        )
        command, env = _global_command(case, fake_home)
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=240,
        )
        output = completed.stdout + completed.stderr
        after = (
            config.is_file(),
            hashlib.sha256(config.read_bytes()).hexdigest(),
        )

        assert completed.returncode not in (0, ABORT_EXIT), output
        assert "forbidden for global install scope" in output
        assert "TEST-ABORT:" not in output
        assert before == after
        assert config.resolve().is_relative_to(fake_home)
        normalized_output = output.replace("\\", "/").lower()
        for live_config in _live_config_metadata():
            assert Path(live_config).resolve().as_posix().lower() not in normalized_output

    assert _live_config_metadata() == live_before
