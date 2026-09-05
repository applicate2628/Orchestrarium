from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest
from tests.fixtures.runtime_capabilities import requires_windows_process_runner


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate-slice-a-detached.py"


def _load():
    assert SCRIPT.is_file(), "detached Slice-A validator owner is missing"
    spec = importlib.util.spec_from_file_location("slice_a_detached_validator", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(
    repo: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _repo(tmp_path: Path) -> tuple[Path, Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "config", "core.eol", "lf")
    _git(repo, "config", "user.email", "slice-a@example.invalid")
    _git(repo, "config", "user.name", "Slice A Test")
    (repo / "tracked.txt").write_text("head\n", encoding="utf-8", newline="\n")
    (repo / "excluded.txt").write_text("head-excluded\n", encoding="utf-8", newline="\n")
    (repo / "probe.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
    (repo / ".gitignore").write_text("/.scratch/\n", encoding="utf-8", newline="\n")
    _git(repo, "add", ".gitignore", "tracked.txt", "excluded.txt", "probe.sh")
    _git(repo, "commit", "-qm", "fixture")
    (repo / "tracked.txt").write_text("overlay\n", encoding="utf-8", newline="\n")
    (repo / "excluded.txt").write_text("concurrent\n", encoding="utf-8", newline="\n")
    baseline = repo / ".scratch" / "legacy-obligation-migration" / "baseline.json"
    baseline.parent.mkdir(parents=True)
    baseline.write_text('{"schemaVersion":1}\n', encoding="utf-8", newline="\n")
    digest = hashlib.sha256(baseline.read_bytes()).hexdigest()
    return repo, baseline, digest


def _command(module, *body: str, timeout: float = 5.0):
    return module.SliceACommand(
        name="fixture-command",
        argv=(sys.executable, "-c", ";".join(body) or "pass"),
        timeout_seconds=timeout,
    )


def _validate(module, repo: Path, run_dir: Path, baseline: Path, digest: str, command):
    return module.validate_slice_a(
        repo_root=repo,
        run_dir=run_dir,
        admitted_paths=("tracked.txt",),
        excluded_paths=("excluded.txt",),
        baseline_path=baseline,
        baseline_sha256=digest,
        commands=(command,),
        validation_scope="unit-fixture",
    )


def _run_direct(module, tmp_path: Path, command):
    attempts = tmp_path / "attempts"
    attempts.mkdir()
    runner = module.ProcessRunnerV1()
    try:
        receipt = module._run_child(runner, command, tmp_path, attempts, 1)
    finally:
        close_result = runner.close()
    assert close_result.outcome == "closed"
    assert close_result.unsettled_run_token_sha256 == ()
    return receipt, attempts


def test_platform_python_commands_canonicalize_absolute_executable_alias(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every Python platform check passes its resolved executable as argv[0]."""

    module = _load()
    canonical_python = Path(sys.executable).resolve()
    python_alias = tmp_path / canonical_python.name
    python_alias.symlink_to(canonical_python)
    monkeypatch.setattr(module.sys, "executable", str(python_alias))

    python_commands = [
        command
        for command in module._platform_commands()
        if command.argv[0] == str(python_alias)
    ]

    assert python_commands
    for command in python_commands:
        executable, actual_argv = module._resolved_argv(command.argv)
        assert executable == canonical_python
        assert actual_argv[0] == str(canonical_python)


def test_git_mapping_preserves_process_supervision_failure_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    supervision = types.SimpleNamespace(
        target_exit_code=None,
        failure_id="PSV1-POSIX-ORACLE-UNAVAILABLE",
        tree=types.SimpleNamespace(tree_empty=False),
        resources_closed=True,
    )
    sink = types.SimpleNamespace(bytes_for=lambda _stream: b"")
    monkeypatch.setattr(
        module,
        "_run_process",
        lambda *_args, **_kwargs: (("git", "status"), {}, sink, supervision),
    )

    with pytest.raises(RuntimeError, match=r"PSV1-POSIX-ORACLE-UNAVAILABLE"):
        module._git(object(), tmp_path, "status")


def _process_running(pid: int) -> bool:
    """Use an operating-system process oracle instead of task-list text."""

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        open_process.restype = wintypes.HANDLE
        wait = kernel32.WaitForSingleObject
        wait.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        wait.restype = wintypes.DWORD
        close = kernel32.CloseHandle
        close.argtypes = [wintypes.HANDLE]
        close.restype = wintypes.BOOL
        handle = open_process(0x00100000, False, pid)
        if not handle:
            return False
        try:
            return wait(handle, 0) == 0x00000102
        finally:
            close(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _receipt_v2(module, **changes):
    values = {
        "schemaVersion": 2,
        "name": "fixture-command",
        "argv": (sys.executable, "-c", "pass"),
        "cwd": ".",
        "environmentKeys": ("PATH",),
        "timeoutSeconds": 5.0,
        "outcome": "success",
        "terminalStage": "completed",
        "failureId": None,
        "exitCode": 0,
        "timedOut": False,
        "cancelled": False,
        "reaped": True,
        "durationSeconds": 0.01,
        "stdoutObservedBytes": 0,
        "stdoutPersistedBytes": 0,
        "stdoutTruncated": False,
        "stdoutSha256": hashlib.sha256(b"").hexdigest(),
        "stderrObservedBytes": 0,
        "stderrPersistedBytes": 0,
        "stderrTruncated": False,
        "stderrSha256": hashlib.sha256(b"").hexdigest(),
        "treeBackend": "windows-job-v1",
        "ownershipConfirmed": True,
        "settlementState": "EMPTY",
        "treeEmpty": True,
        "resourcesClosed": True,
    }
    values.update(changes)
    return module.ChildReceipt(**values)


def test_cli_help_is_side_effect_free() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr
    assert "--platform-only" in result.stdout


def test_detached_adapter_has_one_canonical_process_owner() -> None:
    """Every production child path must route through ProcessRunnerV1."""

    source = SCRIPT.read_text(encoding="utf-8")
    assert "ProcessRunnerV1" in source
    assert "GitResultV1" in source
    assert "import subprocess" not in source
    assert "subprocess." not in source
    assert "subprocess.run(" not in source
    assert "subprocess.Popen(" not in source
    assert "taskkill" not in source.casefold()
    assert "_terminate_process_tree" not in source
    assert "except ModuleNotFoundError" not in source
    assert (
        'if __name__ == "__main__":\n'
        "    from process_supervision.process_runner import ("
    ) in source
    assert (
        "else:\n"
        "    from scripts.process_supervision.process_runner import ("
    ) in source


@requires_windows_process_runner
def test_slice_a_authorization_scope_polarity(
    tmp_path: Path,
) -> None:
    """A successful fixture lifecycle is useful but can never authorize Slice A."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / "success"
    manifest_path = _validate(
        module,
        repo,
        run_dir,
        baseline,
        digest,
        _command(module, "from pathlib import Path", "assert Path('tracked.txt').read_text() == 'overlay\\n'", "assert Path('.git').is_file()", "assert Path('probe.sh').is_file()"),
    )

    assert manifest_path == run_dir / module.TERMINAL_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["result"] == "PASS"
    assert manifest["stableId"] is None
    assert manifest["authorizing"] is False
    assert manifest["publishedAfterCleanup"] is True
    assert manifest["cleanup"]["worktreeRemoved"] is True
    assert not list(repo.parent.glob(".orchestrarium-slice-a-worktree-*"))
    receipts = list((run_dir / "attempts").glob("*.receipt.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text(encoding="utf-8"))["authorizing"] is False
    with pytest.raises(FileExistsError):
        _validate(
            module,
            repo,
            run_dir,
            baseline,
            digest,
            _command(module, "pass"),
        )


def _inject_partial_add(
    module,
    monkeypatch: pytest.MonkeyPatch,
    effect: str,
    *,
    interrupt: bool = False,
) -> tuple[list[Path], object, dict[str, bool]]:
    real_git = module._git
    targets: list[Path] = []
    state = {"registration": False}

    def injected(runner, repo_root: Path, *args: str, check: bool = True):
        if args[:3] == ("worktree", "list", "--porcelain") and state["registration"]:
            payload = (
                f"worktree {targets[0]}\n"
                "HEAD 0000000000000000000000000000000000000000\n"
                "detached\n\n"
            ).encode("utf-8")
            return module.GitResultV1(("git", *args), 0, payload, b"")
        if args[:2] == ("worktree", "remove") and targets:
            state["registration"] = False
            if targets[0].exists():
                shutil.rmtree(targets[0])
            return module.GitResultV1(("git", *args), 0, b"", b"")
        if args[:2] != ("worktree", "add"):
            return real_git(runner, repo_root, *args, check=check)
        worktree = Path(args[-2])
        targets.append(worktree)
        if effect in {"path-only", "both"}:
            worktree.mkdir(parents=True)
            (worktree / "partial.txt").write_text("partial\n", encoding="utf-8")
        if effect in {"registration-only", "both"}:
            state["registration"] = True
        if effect not in {"path-only", "registration-only", "both"}:
            raise AssertionError(effect)
        if interrupt:
            raise KeyboardInterrupt()
        return module.GitResultV1(
            ("git", *args), 1, stdout=b"", stderr=b"injected add failure"
        )

    monkeypatch.setattr(module, "_git", injected)
    return targets, real_git, state


def _cleanup_partial_fixture(repo: Path, worktree: Path) -> None:
    _git(repo, "worktree", "remove", "--force", str(worktree), check=False)
    if worktree.exists() or worktree.is_symlink():
        shutil.rmtree(worktree, ignore_errors=True)
    _git(repo, "worktree", "prune", "--expire", "now", check=False)


def _failed_add_validation(module, repo, baseline, digest, run_dir):
    return module.validate_slice_a(
        repo_root=repo,
        run_dir=run_dir,
        admitted_paths=("tracked.txt",),
        excluded_paths=("excluded.txt",),
        baseline_path=baseline,
        baseline_sha256=digest,
        commands=(_command(module, "pass"),),
        validation_scope="unit-fixture",
    )


@requires_windows_process_runner
def test_worktree_add_nonzero_path_only_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    targets, real_git, state = _inject_partial_add(module, monkeypatch, "path-only")
    try:
        manifest = _failed_add_validation(
            module, repo, baseline, digest, repo / ".scratch" / "runs" / "path-only"
        )
        assert manifest is None
        assert len(targets) == 1
        assert not targets[0].exists()
        assert state["registration"] is False
    finally:
        if targets:
            _cleanup_partial_fixture(repo, targets[0])


@requires_windows_process_runner
def test_worktree_add_nonzero_registration_only_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    targets, real_git, state = _inject_partial_add(
        module, monkeypatch, "registration-only"
    )
    try:
        manifest = _failed_add_validation(
            module,
            repo,
            baseline,
            digest,
            repo / ".scratch" / "runs" / "registration-only",
        )
        assert manifest is None
        assert len(targets) == 1
        assert not targets[0].exists()
        assert state["registration"] is False
    finally:
        if targets:
            _cleanup_partial_fixture(repo, targets[0])


@requires_windows_process_runner
def test_worktree_add_nonzero_both_side_effects_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    targets, real_git, state = _inject_partial_add(module, monkeypatch, "both")
    try:
        manifest = _failed_add_validation(
            module, repo, baseline, digest, repo / ".scratch" / "runs" / "both"
        )
        assert manifest is None
        assert len(targets) == 1
        assert not targets[0].exists()
        assert state["registration"] is False
    finally:
        if targets:
            _cleanup_partial_fixture(repo, targets[0])


@requires_windows_process_runner
def test_worktree_add_interruption_partial_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    targets, real_git, state = _inject_partial_add(
        module, monkeypatch, "both", interrupt=True
    )
    run_dir = repo / ".scratch" / "runs" / "interrupted-add"
    try:
        with pytest.raises(KeyboardInterrupt):
            _failed_add_validation(module, repo, baseline, digest, run_dir)
        assert len(targets) == 1
        assert not targets[0].exists()
        assert state["registration"] is False
        assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()
    finally:
        if targets:
            _cleanup_partial_fixture(repo, targets[0])


@requires_windows_process_runner
def test_partial_acquisition_cleanup_failure_manifest_is_durable_before_interrupt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    targets, real_git, _state = _inject_partial_add(
        module, monkeypatch, "path-only", interrupt=True
    )
    real_rmtree = module.shutil.rmtree

    def fail_partial_remove(path, *args, **kwargs):
        if targets and Path(path) == targets[0]:
            raise OSError("injected partial cleanup failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "rmtree", fail_partial_remove)
    run_dir = repo / ".scratch" / "runs" / "interrupted-cleanup-failure"
    try:
        with pytest.raises(KeyboardInterrupt):
            _failed_add_validation(module, repo, baseline, digest, run_dir)
        manifest_path = run_dir / module.TERMINAL_MANIFEST_NAME
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["result"] == "NON_PASS"
        assert manifest["stableId"] == "E_SLICE_A_VALIDATION_CLEANUP_FAILED"
        assert manifest["authorizing"] is False
        assert manifest["cleanup"]["pathPresent"] is True
        assert manifest["cleanup"]["registrationPresent"] is False
        assert manifest["recoveryPath"] == str(targets[0])
        assert "KeyboardInterrupt" in manifest["originalCause"]
    finally:
        monkeypatch.setattr(module.shutil, "rmtree", real_rmtree)
        if targets:
            _cleanup_partial_fixture(repo, targets[0])


@requires_windows_process_runner
def test_deep_evidence_directory_uses_a_bounded_workspace_worktree_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows path length must depend on repo scratch, not the evidence nesting."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    real_git = module._git
    targets: list[Path] = []

    def observed_git(runner, repo_root: Path, *args: str, check: bool = True):
        if args[:2] == ("worktree", "add"):
            targets.append(Path(args[-2]))
        return real_git(runner, repo_root, *args, check=check)

    monkeypatch.setattr(module, "_git", observed_git)
    run_dir = repo / ".scratch" / ("deep-evidence-segment-" * 8) / "run"
    manifest_path = _validate(
        module,
        repo,
        run_dir,
        baseline,
        digest,
        _command(module, "pass"),
    )
    assert manifest_path.is_file()
    assert len(targets) == 1
    worktree = targets[0]
    assert worktree.parent.parent == repo.parent
    assert worktree.parent.name.startswith(".orchestrarium-slice-a-worktree-")
    assert worktree.name == "candidate"
    assert not worktree.is_relative_to(repo / ".scratch")
    assert len(str(worktree)) < len(str(run_dir / "worktree"))
    assert not worktree.exists()


@requires_windows_process_runner
def test_child_failure_has_attempt_receipt_but_no_terminal_manifest(
    tmp_path: Path,
) -> None:
    """A non-zero child remains attempt evidence and cannot publish a manifest."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / "child-failure"
    manifest = _validate(
        module,
        repo,
        run_dir,
        baseline,
        digest,
        _command(module, "import sys", "sys.exit(7)"),
    )

    assert manifest is None
    assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()
    receipt_path = next((run_dir / "attempts").glob("*.receipt.json"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["authorizing"] is False
    assert receipt["reaped"] is True
    assert receipt["exitCode"] == 7


@requires_windows_process_runner
def test_real_child_timeout_is_reaped(tmp_path: Path) -> None:
    """A deadline produces bounded, settled version-2 evidence."""

    module = _load()
    receipt, attempts = _run_direct(
        module,
        tmp_path,
        _command(module, "import time", "time.sleep(5)", timeout=0.05),
    )
    assert receipt.schemaVersion == 2
    assert receipt.timedOut is True
    assert receipt.reaped is True
    assert receipt.terminalStage == "deadline"
    assert receipt.failureId == "PSV1-DEADLINE"
    assert receipt.treeEmpty is True
    assert receipt.settlementState == "EMPTY"
    assert receipt.resourcesClosed is True
    assert not list(attempts.glob("*.stdout.log"))
    assert not list(attempts.glob("*.stderr.log"))


@requires_windows_process_runner
def test_exact_argv_reaches_real_child(tmp_path: Path) -> None:
    """Empty, quoted, slash-heavy, spaced, and Unicode argv remain exact."""

    module = _load()
    observed = tmp_path / "observed-argv.json"
    expected = (
        "",
        "two words",
        'quote"inside',
        'backslashes\\before"quote',
        "C:\\path with space\\",
        "Москва-测试",
    )
    command = module.SliceACommand(
        name="exact-argv",
        argv=(
            sys.executable,
            "-c",
            "import json,sys;from pathlib import Path;"
            "Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:], ensure_ascii=False), encoding='utf-8')",
            str(observed),
            *expected,
        ),
        timeout_seconds=5.0,
    )
    receipt, _attempts = _run_direct(module, tmp_path, command)
    assert receipt.failureId is None
    assert receipt.exitCode == 0
    assert receipt.argv == command.argv
    assert receipt.cwd == "."
    assert receipt.environmentKeys == tuple(sorted(module._child_environment()))
    assert json.loads(observed.read_text(encoding="utf-8")) == list(expected)


@requires_windows_process_runner
def test_infinite_output_is_bounded_and_settled(tmp_path: Path) -> None:
    """Capture overflow stops the whole run without an unbounded target spool."""

    module = _load()
    command = _command(
        module,
        "import os",
        "exec(\"while True:\\n os.write(1, b'x' * 65536)\")",
        timeout=5.0,
    )
    receipt, attempts = _run_direct(module, tmp_path, command)
    assert receipt.failureId == "PSV1-CAPTURE-LIMIT"
    assert receipt.terminalStage == "capture-limit"
    assert receipt.stdoutObservedBytes > receipt.stdoutPersistedBytes
    assert receipt.stdoutPersistedBytes <= 1024 * 1024
    assert receipt.stdoutTruncated is True
    assert receipt.treeEmpty is True
    assert receipt.resourcesClosed is True
    assert sum(path.stat().st_size for path in attempts.iterdir()) < 128 * 1024


@requires_windows_process_runner
def test_fast_oversized_git_status_cannot_be_consumed_as_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A truncated Git status prefix cannot be accepted as exact repository state."""

    module = _load()
    from scripts.process_supervision import process_runner

    limit = 64
    policy = process_runner.CapturePolicyV1(
        "detached-fast-git-v1",
        limit,
        limit,
        limit,
        limit,
    )
    monkeypatch.setattr(
        module.ValidatorCapturePolicyV1,
        "to_capture_policy",
        lambda _self: policy,
    )
    complete_status = b"?? " + (b"a" * 60) + b"\0?? b\0"
    observed = []

    def backend_factory(_runner, _lifecycle):
        def backend(
            request, _owned_lifecycle, _validated_cwd, _launch_owner
        ):
            capture = process_runner.BoundedCaptureV1(
                request.capture_policy, request.capture_sink_binding
            )
            capture.feed("stdout", complete_status)
            result = process_runner._result_from_parts(
                request,
                time.monotonic(),
                executable_identity_sha256=(
                    _validated_cwd.executable_identity_sha256
                ),
                backend="controlled-fast-git-v1",
                capture=capture,
                stdin_state={"written": 0, "complete": True},
                exit_code=0,
                failure_id=None,
                stage="completed",
                timed_out=False,
                cancelled=False,
                ownership_confirmed=True,
                settlement_state="EMPTY",
                direct_reaped=True,
                primary_thread_closed=True,
                job_handle_closed=True,
                resources_closed=True,
                poisoned=False,
                cleanup_issues=(),
            )
            observed.append(result)
            return result

        return backend

    runner = module.ProcessRunnerV1(backend_factory=backend_factory)
    try:
        with pytest.raises(RuntimeError, match=r"git status .* failed"):
            module._status(runner, tmp_path)
    finally:
        close_result = runner.close()

    assert close_result.outcome == "closed"
    assert len(observed) == 1
    assert observed[0].outcome == "supervisor-failure"
    assert observed[0].failure_id == "PSV1-CAPTURE-LIMIT"
    assert observed[0].stdout.truncated is True


@requires_windows_process_runner
def test_timeout_settles_parent_and_descendant(tmp_path: Path) -> None:
    """A timed-out parent cannot leave its sleeping descendant alive."""

    module = _load()
    descendant_pid = tmp_path / "descendant-timeout.pid"
    body = (
        "import subprocess,sys,time",
        "from pathlib import Path",
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])",
        "Path(sys.argv[1]).write_text(str(child.pid), encoding='ascii')",
        "time.sleep(30)",
    )
    command = module.SliceACommand(
        name="orphan-timeout",
        argv=(sys.executable, "-c", ";".join(body), str(descendant_pid)),
        timeout_seconds=0.5,
    )
    receipt, _attempts = _run_direct(module, tmp_path, command)
    pid = int(descendant_pid.read_text(encoding="ascii"))
    assert receipt.failureId == "PSV1-DEADLINE"
    assert receipt.treeEmpty is True
    assert receipt.reaped is True
    assert not _process_running(pid)


@requires_windows_process_runner
def test_direct_exit_with_retained_pipe_settles_descendant(tmp_path: Path) -> None:
    """A descendant retaining both capture pipes cannot outlive the receipt."""

    module = _load()
    descendant_pid = tmp_path / "descendant-retained-pipe.pid"
    body = (
        "import subprocess,sys",
        "from pathlib import Path",
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])",
        "Path(sys.argv[1]).write_text(str(child.pid), encoding='ascii')",
    )
    command = module.SliceACommand(
        name="retained-pipe",
        argv=(sys.executable, "-c", ";".join(body), str(descendant_pid)),
        timeout_seconds=15.0,
    )
    receipt, _attempts = _run_direct(module, tmp_path, command)
    pid = int(descendant_pid.read_text(encoding="ascii"))
    assert receipt.failureId == "PSV1-TREE-SETTLEMENT"
    assert receipt.terminalStage == "tree-settlement"
    assert receipt.treeEmpty is True
    assert receipt.resourcesClosed is True
    assert not _process_running(pid)


@requires_windows_process_runner
def test_timed_out_receipt_with_clean_cleanup_has_no_terminal_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completed timeout receipt cannot become focused PASS after clean cleanup."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / "timed-out-receipt"
    receipt = _receipt_v2(
        module,
        outcome="supervisor-failure",
        terminalStage="deadline",
        failureId="PSV1-DEADLINE",
        exitCode=-1,
        timedOut=True,
    )

    def timed_out_receipt(_runner, _command, _worktree, attempts, ordinal, **_kwargs):
        module._atomic_json(
            attempts / f"{ordinal:02d}-fixture-command.receipt.json",
            module._receipt_payload(receipt),
        )
        return receipt

    monkeypatch.setattr(module, "_run_child", timed_out_receipt)
    manifest = _validate(
        module, repo, run_dir, baseline, digest, _command(module, "pass")
    )
    assert manifest is None
    assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()
    assert not list(repo.parent.glob(".orchestrarium-slice-a-worktree-*"))


@pytest.mark.parametrize("mode", ("missing", "spool-open"))
@requires_windows_process_runner
def test_missing_or_unclosed_receipt_fails_without_terminal_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Null receipts and unclosed spools cannot be interpreted as a clean child."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / mode
    if mode == "missing":
        result = None
    else:
        result = _receipt_v2(
            module,
            resourcesClosed=False,
        )
    def incomplete_receipt(_runner, _command, _worktree, attempts, ordinal, **_kwargs):
        if result is not None:
            module._atomic_json(
                attempts / f"{ordinal:02d}-fixture-command.receipt.json",
                module._receipt_payload(result),
            )
        return result

    monkeypatch.setattr(module, "_run_child", incomplete_receipt)
    manifest = _validate(
        module, repo, run_dir, baseline, digest, _command(module, "pass")
    )
    assert manifest is None
    assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()


def test_legacy_v1_receipt_is_readable_but_nonauthorizing(tmp_path: Path) -> None:
    """Compatibility may describe v1 evidence but can never promote it to current."""

    module = _load()
    receipt_path = tmp_path / "legacy.receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "name": "fixture-command",
                "argv": [sys.executable, "-c", "pass"],
                "cwd": ".",
                "environmentKeys": ["PATH"],
                "timeoutSeconds": 5.0,
                "exitCode": 0,
                "timedOut": False,
                "cancelled": False,
                "reaped": True,
                "spoolsClosed": True,
                "durationSeconds": 0.01,
                "stdoutSha256": "0" * 64,
                "stderrSha256": "0" * 64,
                "authorizing": False,
            }
        ),
        encoding="utf-8",
    )
    loaded = module._read_receipt(receipt_path)
    summary = module._receipt_summary(loaded)
    assert summary["schemaVersion"] == 1
    assert summary["legacy"] is True
    assert summary["currentEvidence"] is False
    assert summary["authorizing"] is False


@requires_windows_process_runner
def test_receipt_drift_denies_terminal_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The persisted receipt, not an in-memory pre-drift object, owns evidence."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / "receipt-drift"
    real_run = module._run_child

    def drift_receipt(*args, **kwargs):
        receipt = real_run(*args, **kwargs)
        receipt_path = run_dir / "attempts" / "01-fixture-command.receipt.json"
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload["stdoutSha256"] = "f" * 64
        receipt_path.write_text(json.dumps(payload), encoding="utf-8")
        return receipt

    monkeypatch.setattr(module, "_run_child", drift_receipt)
    manifest = _validate(
        module, repo, run_dir, baseline, digest, _command(module, "pass")
    )
    assert manifest is None
    assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()
    error = json.loads(
        (run_dir / "attempts" / "supervisor-error.json").read_text(encoding="utf-8")
    )
    assert error["stableId"] == "E_SLICE_A_VALIDATION_INCOMPLETE"


@requires_windows_process_runner
def test_shell_census_omission_fails_before_child_and_without_manifest(
    tmp_path: Path
) -> None:
    """A detached copy that loses a tracked shell entrypoint is not faithful."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    (repo / "probe.sh").unlink()
    run_dir = repo / ".scratch" / "runs" / "shell-omission"
    manifest = module.validate_slice_a(
        repo_root=repo,
        run_dir=run_dir,
        admitted_paths=("tracked.txt", "probe.sh"),
        excluded_paths=("excluded.txt",),
        baseline_path=baseline,
        baseline_sha256=digest,
        commands=(_command(module, "pass"),),
        validation_scope="unit-fixture",
    )
    assert manifest is None
    assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()


@requires_windows_process_runner
def test_explicit_untracked_exclusion_is_absent_from_detached_worktree(
    tmp_path: Path,
) -> None:
    """Concurrent untracked notes are classified but never copied into evidence."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    concurrent = repo / ".superpowers" / "concurrent.md"
    concurrent.parent.mkdir()
    concurrent.write_text("unrelated\n", encoding="utf-8")
    run_dir = repo / ".scratch" / "runs" / "untracked-exclusion"
    manifest_path = module.validate_slice_a(
        repo_root=repo,
        run_dir=run_dir,
        admitted_paths=("tracked.txt",),
        excluded_paths=("excluded.txt",),
        ignored_untracked_paths=(".superpowers/concurrent.md",),
        baseline_path=baseline,
        baseline_sha256=digest,
        commands=(
            _command(
                module,
                "from pathlib import Path",
                "assert not Path('.superpowers/concurrent.md').exists()",
            ),
        ),
        validation_scope="unit-fixture",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["result"] == "PASS"
    assert manifest["excludedUntracked"] == [
        {"path": ".superpowers/concurrent.md", "status": "??"}
    ]


@requires_windows_process_runner
def test_cleanup_failure_publishes_one_nonpass_with_recovery_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cleanup failure must never leave a preliminary PASS to overwrite."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / "cleanup-failure"
    real_remove = module._remove_worktree
    retained: list[Path] = []

    def fail_remove(runner, repo_root: Path, worktree: Path):
        retained.append(worktree)
        return module.CleanupOutcome(
            worktree_removed=False,
            registration_removed=False,
            failures=(f"worktree-remove:{tmp_path / 'private-machine-path'}",),
            recovery_path=str(worktree),
        )

    monkeypatch.setattr(module, "_remove_worktree", fail_remove)
    try:
        manifest_path = _validate(
            module, repo, run_dir, baseline, digest, _command(module, "pass")
        )
        assert manifest_path is not None
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["result"] == "NON_PASS"
        assert manifest["stableId"] == "E_SLICE_A_VALIDATION_CLEANUP_FAILED"
        assert manifest["authorizing"] is False
        assert manifest["recoveryPath"] == str(retained[0])
        assert manifest["cleanup"]["failures"] == [
            "worktree-remove",
            "worktree-path-remains",
            "worktree-registration-remains",
        ]
        assert str(tmp_path / "private-machine-path") not in json.dumps(manifest)
        assert not list(run_dir.glob("*.tmp"))
    finally:
        monkeypatch.setattr(module, "_remove_worktree", real_remove)
        assert len(retained) == 1
        _cleanup_partial_fixture(repo, retained[0])


@pytest.mark.parametrize("boundary", ("child", "publication"))
@requires_windows_process_runner
def test_interruption_before_publication_leaves_no_terminal_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    """An interruption cannot expose a terminal result at either boundary."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    run_dir = repo / ".scratch" / "runs" / f"interrupt-{boundary}"
    if boundary == "child":
        monkeypatch.setattr(
            module,
            "_run_child",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
    else:
        monkeypatch.setattr(
            module,
            "_atomic_publish",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
    with pytest.raises(KeyboardInterrupt):
        _validate(module, repo, run_dir, baseline, digest, _command(module, "pass"))
    assert not (run_dir / module.TERMINAL_MANIFEST_NAME).exists()


@pytest.mark.parametrize(
    "scope", ("unit-fixture", "platform-final-correction-a", "slice-a-final")
)
@requires_windows_process_runner
def test_detached_manifest_always_nonauthorizing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scope: str
) -> None:
    """Catches machine authority or raw/local evidence in a successful manifest."""

    module = _load()
    repo, baseline, digest = _repo(tmp_path)
    command = _command(module, "pass")
    arguments = {
        "repo_root": repo,
        "run_dir": repo / ".scratch" / "runs" / f"nonauthorizing-{scope}",
        "admitted_paths": ("tracked.txt",),
        "excluded_paths": ("excluded.txt",),
        "baseline_path": baseline,
        "baseline_sha256": digest,
        "commands": (command,),
        "validation_scope": scope,
    }
    if scope != "unit-fixture":
        design = tmp_path / f"{scope}-design.md"
        design.write_text("accepted reset design\n", encoding="utf-8")
        design_digest = hashlib.sha256(design.read_bytes()).hexdigest()
        monkeypatch.setattr(module, "_validate_design_currency", lambda *_args: None)
        arguments.update(
            design_path=design,
            design_sha256=design_digest,
        )
    manifest_path = module.validate_slice_a(
        **arguments,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["authorizing"] is False
    assert "worktreePath" not in manifest
    assert "fullSuiteComparison" not in manifest
    assert "baselineRun" not in manifest
    assert "candidateRun" not in manifest
    encoded = json.dumps(manifest, sort_keys=True).casefold()
    assert "environmenttemplate" not in encoded
    assert "longrepr" not in encoded
    for receipt in manifest["receipts"]:
        assert "argv" not in receipt
        assert "cwd" not in receipt
        assert "stdout" not in receipt
        assert "stderr" not in receipt
        assert len(receipt["argvSha256"]) == 64
        assert len(receipt["stdoutSha256"]) == 64
        assert len(receipt["stderrSha256"]) == 64
    assert str(tmp_path) not in json.dumps(manifest, sort_keys=True)
    assert sys.executable not in json.dumps(manifest, sort_keys=True)


def test_r4_authority_surfaces_removed() -> None:
    """Catches reintroduction of the removed candidate-controlled authority owners."""

    module = _load()
    for symbol in (
        "FullSuiteComparisonV1",
        "_FULL_SUITE_HOOK_SOURCE",
        "_derive_exercise_map",
        "_run_paired_full_suites",
        "_load_full_suite_hook",
        "_full_suite_run_record",
    ):
        assert not hasattr(module, symbol), symbol
    assert not list((ROOT / "tests" / "fixtures" / "luna").rglob("*.json"))


@pytest.mark.skipif(os.name != "posix", reason="generic POSIX runner refusal")
def test_unsupported_posix_runner_does_not_execute_or_authorize_child(tmp_path: Path) -> None:
    module = _load()
    marker = tmp_path / "must-not-exist"
    receipt, _attempts = _run_direct(
        module, tmp_path,
        _command(module, "from pathlib import Path", f"Path({str(marker)!r}).write_text('started')"),
    )
    assert receipt.failureId == "PSV1-POSIX-ORACLE-UNAVAILABLE"
    assert receipt.authorizing is False
    assert receipt.ownershipConfirmed is False
    assert receipt.resourcesClosed is True
    assert not marker.exists()
