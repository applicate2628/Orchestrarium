"""Deterministic contract tests for the Claude-line Codex dispatch watcher."""

from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WATCH_SH = ROOT / "src.claude" / "agents" / "scripts" / "await-codex-dispatch.sh"
WATCH_PS1 = ROOT / "src.claude" / "agents" / "scripts" / "await-codex-dispatch.ps1"
INVOKE_SH = ROOT / "src.claude" / "agents" / "scripts" / "invoke-codex-prompt.sh"
INVOKE_PS1 = ROOT / "src.claude" / "agents" / "scripts" / "invoke-codex-prompt.ps1"
CLAUDE_INVOKE_SH = ROOT / "src.claude" / "agents" / "scripts" / "invoke-claude-prompt.sh"
CLAUDE_INVOKE_PS1 = ROOT / "src.claude" / "agents" / "scripts" / "invoke-claude-prompt.ps1"


def _bash() -> str | None:
    found = shutil.which("bash")
    if found and "System32" not in found:
        return found
    for candidate in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return found


def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _posix_path(path: Path) -> str:
    value = str(path).replace("\\", "/")
    if len(value) > 1 and value[1] == ":":
        value = "/" + value[0].lower() + value[2:]
    return value


def _run_sh(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    bash = _bash()
    if not bash:
        pytest.skip("bash is unavailable")
    return subprocess.run(
        [bash, _posix_path(WATCH_SH), *args],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        encoding="ascii",
        timeout=10,
    )


def _run_ps(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    powershell = _powershell()
    if not powershell:
        pytest.skip("PowerShell is unavailable")
    return subprocess.run(
        [
            powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(WATCH_PS1), *args,
        ],
        cwd=cwd or ROOT,
        capture_output=True,
        text=True,
        encoding="ascii",
        timeout=10,
    )


def _init_git_fixture(root: Path) -> str:
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / "state.txt").write_text("initial\n", encoding="ascii")
    subprocess.run(["git", "-C", str(root), "add", "state.txt"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=watcher-test", "-c", "user.email=watcher@test.invalid", "commit", "-qm", "initial"],
        check=True,
        capture_output=True,
    )
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def _assert_one_line(
    result: subprocess.CompletedProcess[str], prefix: str, expected_returncode: int = 0
) -> str:
    assert result.returncode == expected_returncode, (
        f"expected exit {expected_returncode} for a {prefix!r} terminal status; "
        f"got {result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    lines = result.stdout.splitlines()
    assert len(lines) == 1, result.stdout
    assert lines[0].startswith(prefix), result.stdout
    return lines[0]


def test_non_empty_out_is_done(tmp_path: Path) -> None:
    out = tmp_path / "dispatch.out"
    out.write_text("GATE: PASS\n", encoding="ascii")

    line = _assert_one_line(
        _run_sh("--out", _posix_path(out), "--poll-secs", "0.05", "--max-secs", "2"),
        "DONE out=",
    )
    assert line == f"DONE out={len(out.read_bytes())}"


def test_non_empty_lastmsg_is_done(tmp_path: Path) -> None:
    out = tmp_path / "dispatch.out"
    lastmsg = tmp_path / "dispatch.lastmsg"
    lastmsg.write_text("GATE: PASS\n", encoding="ascii")

    line = _assert_one_line(
        _run_sh(
            "--out", _posix_path(out), "--lastmsg", _posix_path(lastmsg),
            "--poll-secs", "0.05", "--max-secs", "2",
        ),
        "DONE lastmsg=",
    )
    assert line == f"DONE lastmsg={len(lastmsg.read_bytes())}"


def test_commit_base_change_is_done(tmp_path: Path) -> None:
    base = _init_git_fixture(tmp_path)
    out = tmp_path / "dispatch.out"
    process = None
    bash = _bash()
    if not bash:
        pytest.skip("bash is unavailable")
    process = subprocess.Popen(
        [
            bash, _posix_path(WATCH_SH), "--out", _posix_path(out),
            "--commit-base", base, "--poll-secs", "0.05", "--max-secs", "4",
        ],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="ascii",
    )
    time.sleep(0.25)
    (tmp_path / "state.txt").write_text("committed\n", encoding="ascii")
    subprocess.run(["git", "-C", str(tmp_path), "add", "state.txt"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=watcher-test", "-c", "user.email=watcher@test.invalid", "commit", "-qm", "worker"],
        check=True,
        capture_output=True,
    )
    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0, stderr
    assert stdout.splitlines() == [f"DONE committed={subprocess.check_output(['git', '-C', str(tmp_path), 'rev-parse', 'HEAD'], text=True).strip()}"]


def test_err_idle_is_stall(tmp_path: Path) -> None:
    out = tmp_path / "dispatch.out"
    err = tmp_path / "dispatch.err"
    err.write_text("provider started\n", encoding="ascii")
    old = time.time() - 5
    os.utime(err, (old, old))

    line = _assert_one_line(
        _run_sh(
            "--out", _posix_path(out), "--err", _posix_path(err),
            "--stall-secs", "1", "--poll-secs", "0.05", "--max-secs", "3",
        ),
        "STALL err-idle=",
        expected_returncode=75,
    )
    assert int(line.split("=", 1)[1]) >= 1


def test_max_elapsed_is_timeout(tmp_path: Path) -> None:
    out = tmp_path / "dispatch.out"

    line = _assert_one_line(
        _run_sh(
            "--out", _posix_path(out), "--poll-secs", "0.05", "--max-secs", "1",
        ),
        "TIMEOUT max=",
        expected_returncode=124,
    )
    assert line == "TIMEOUT max=1"


def test_terminal_status_exit_codes_are_distinct_and_machine_readable(tmp_path: Path) -> None:
    """Regression lock for the liveness-invariant bug: a caller testing $?/exit
    code alone (never reading stdout) must be able to tell DONE from a stall or
    a timeout. Before the fix, DONE/STALL/TIMEOUT all exited 0 -- a caller
    could not distinguish a delivered review from a 45-minute stall by exit
    code (work-items/bugs/2026-07-26-await-codex-dispatch-cannot-satisfy-its-
    own-liveness-invariant.md)."""
    out = tmp_path / "dispatch.out"
    out.write_text("GATE: PASS\n", encoding="ascii")
    done = _run_sh("--out", _posix_path(out), "--poll-secs", "0.05", "--max-secs", "2")
    assert done.returncode == 0, done.stderr

    err = tmp_path / "dispatch.err"
    err.write_text("provider started\n", encoding="ascii")
    old = time.time() - 5
    os.utime(err, (old, old))
    stall = _run_sh(
        "--out", _posix_path(tmp_path / "missing.out"), "--err", _posix_path(err),
        "--stall-secs", "1", "--poll-secs", "0.05", "--max-secs", "3",
    )
    assert stall.returncode == 75, stall.stderr

    timeout = _run_sh(
        "--out", _posix_path(tmp_path / "missing.out"), "--poll-secs", "0.05", "--max-secs", "1",
    )
    assert timeout.returncode == 124, timeout.stderr

    # All three terminal codes must be pairwise distinct AND distinct from the
    # existing usage-error code (2, unchanged) -- the whole point is that a
    # caller can tell all four apart from $? alone.
    codes = {"done": done.returncode, "stall": stall.returncode, "timeout": timeout.returncode, "usage": 2}
    assert len(set(codes.values())) == len(codes), codes


def test_powershell_port_covers_terminal_matrix(tmp_path: Path) -> None:
    if not _powershell():
        pytest.skip("PowerShell is unavailable")

    out = tmp_path / "dispatch.out"
    out.write_text("GATE: PASS\n", encoding="ascii")
    line = _run_ps("-Out", str(out), "-PollSecs", "0.05", "-MaxSecs", "2")
    assert line.returncode == 0, line.stderr
    assert line.stdout.splitlines() == [f"DONE out={len(out.read_bytes())}"]

    lastmsg = tmp_path / "dispatch.lastmsg"
    lastmsg.write_text("GATE: PASS\n", encoding="ascii")
    line = _run_ps(
        "-Out", str(tmp_path / "missing.out"), "-LastMsg", str(lastmsg),
        "-PollSecs", "0.05", "-MaxSecs", "2",
    )
    assert line.returncode == 0, line.stderr
    assert line.stdout.splitlines() == [f"DONE lastmsg={len(lastmsg.read_bytes())}"]

    err = tmp_path / "dispatch.err"
    err.write_text("provider started\n", encoding="ascii")
    old = time.time() - 5
    os.utime(err, (old, old))
    line = _run_ps(
        "-Out", str(tmp_path / "missing.out"), "-Err", str(err),
        "-StallSecs", "1", "-PollSecs", "0.05", "-MaxSecs", "3",
    )
    assert line.returncode == 75, line.stderr
    assert line.stdout.startswith("STALL err-idle=")

    line = _run_ps(
        "-Out", str(tmp_path / "missing.out"), "-PollSecs", "0.05", "-MaxSecs", "1",
    )
    assert line.returncode == 124, line.stderr
    assert line.stdout.splitlines() == ["TIMEOUT max=1"]

    repo = tmp_path / "git-fixture"
    repo.mkdir()
    base = _init_git_fixture(repo)
    process = subprocess.Popen(
        [
            _powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(WATCH_PS1), "-Out", str(repo / "missing.out"),
            "-CommitBase", base, "-PollSecs", "0.05", "-MaxSecs", "4",
        ],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="ascii",
    )
    time.sleep(0.25)
    (repo / "state.txt").write_text("committed\n", encoding="ascii")
    subprocess.run(["git", "-C", str(repo), "add", "state.txt"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=watcher-test", "-c", "user.email=watcher@test.invalid", "commit", "-qm", "worker"],
        check=True,
        capture_output=True,
    )
    stdout, stderr = process.communicate(timeout=5)
    assert process.returncode == 0, stderr
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    assert stdout.splitlines() == [f"DONE committed={head}"]


def test_both_wrappers_emit_active_watch_command_after_paths() -> None:
    shell = INVOKE_SH.read_text(encoding="utf-8")
    powershell = INVOKE_PS1.read_text(encoding="utf-8")
    note = "actively await this dispatch (do NOT passively wait for a notification):"

    assert note in shell
    assert shell.index('echo "$LASTMSG_PATH"') < shell.index(note)
    assert shell.index('echo "$PROMPT_PATH"') < shell.index('"$CODEX_CMD" exec')
    assert "await-codex-dispatch.sh" in shell
    assert '$(dirname "$0")/await-codex-dispatch.sh' in shell
    assert "--out" in shell and "--err" in shell and "--lastmsg" in shell
    assert "--stall-secs 2700" in shell

    assert note in powershell
    assert powershell.index("Write-Output $lastmsgPath") < powershell.index(note)
    assert powershell.index("Write-Output $promptPath") < powershell.index("$promptBody | & $codexPath exec")
    assert "await-codex-dispatch.ps1" in powershell
    assert "Join-Path $PSScriptRoot 'await-codex-dispatch.ps1'" in powershell
    assert "-Out" in powershell and "-Err" in powershell and "-LastMsg" in powershell
    assert "-StallSecs 2700" in powershell


def test_bash_wrapper_prints_copy_pasteable_watch_command(tmp_path: Path) -> None:
    bash = _bash()
    if not bash:
        pytest.skip("bash is unavailable")

    fake = tmp_path / "fake-codex.sh"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "lastmsg=''\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  case \"$1\" in\n"
        "    --output-last-message) lastmsg=\"$2\"; shift 2 ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "cat >/dev/null\n"
        "printf 'GATE: PASS\\n' > \"$lastmsg\"\n",
        encoding="ascii",
        newline="\n",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("watcher test\n", encoding="ascii")
    output_dir = tmp_path / "outputs"
    env = os.environ.copy()
    env["CODEX_BIN"] = _posix_path(fake)
    env["CODEX_PROMPTS_DIR"] = _posix_path(output_dir)

    result = subprocess.run(
        [bash, _posix_path(INVOKE_SH), "watcher-test", "--prompt-file", _posix_path(prompt)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="ascii",
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[-2] == "# actively await this dispatch (do NOT passively wait for a notification):"
    command = lines[-1]
    expected_watcher = _posix_path(INVOKE_SH.parent / "await-codex-dispatch.sh")
    assert command.startswith(f"bash {shlex.quote(expected_watcher)}")
    assert f"--out {shlex.quote(lines[1])}" in command
    assert f"--err {shlex.quote(lines[2])}" in command
    assert f"--lastmsg {shlex.quote(lines[3])}" in command


def test_powershell_watcher_port_names_required_primitives() -> None:
    source = WATCH_PS1.read_text(encoding="utf-8")
    assert "Get-Date" in source
    assert "Test-Path" in source
    assert "LastWriteTime" in source
    assert "Write-Output" in source
    assert "Start-Sleep -Milliseconds" in source
    assert "<#[" not in source
    assert "]#>" not in source


def test_powershell_watcher_usage_errors_are_stderr(tmp_path: Path) -> None:
    if not _powershell():
        pytest.skip("PowerShell is unavailable")

    missing_out = _run_ps("-PollSecs", "0.05", "-MaxSecs", "1")
    assert missing_out.returncode == 2
    assert missing_out.stdout == ""
    assert "FAIL: --out is required" in missing_out.stderr
    assert "Usage:" in missing_out.stderr

    invalid_timing = _run_ps(
        "-Out", str(tmp_path / "dispatch.out"), "-PollSecs", "-1",
    )
    assert invalid_timing.returncode == 2
    assert invalid_timing.stdout == ""
    assert "FAIL: timing values must be non-negative" in invalid_timing.stderr


def test_claude_prompt_wrappers_scope_dispatched_review_marker() -> None:
    shell = CLAUDE_INVOKE_SH.read_text(encoding="utf-8")
    powershell = CLAUDE_INVOKE_PS1.read_text(encoding="utf-8")

    assert "export ORCHESTRARIUM_DISPATCHED_REVIEW=1" in shell
    claude_call = '"$CLAUDE_CMD" "${CLAUDE_FLAGS[@]}"'
    assert shell.index("export ORCHESTRARIUM_DISPATCHED_REVIEW=1") < shell.index(claude_call)
    assert "$env:ORCHESTRARIUM_DISPATCHED_REVIEW" in powershell
    assert "Remove-Item Env:ORCHESTRARIUM_DISPATCHED_REVIEW" in powershell
    assert powershell.index("$env:ORCHESTRARIUM_DISPATCHED_REVIEW") < powershell.index("$promptBody | & $claudePath")


# --- Direct liveness probe (--pid-file / -PidFile) -------------------------
#
# Regression coverage for the still-open half of work-items/bugs/2026-07-26-
# await-codex-dispatch-cannot-satisfy-its-own-liveness-invariant.md: the
# watcher previously inferred everything from artifact timestamps and could
# never observe a process that died silently -- exactly the live incident's
# shape (8 of 16 provider runs producing zero-byte output, indistinguishable
# from "still working" for the full 45-60 minute stall/timeout window).


def _write_pid_file(path: Path, pid: int | str, start: str | None = None) -> None:
    lines = [f"pid={pid}"]
    if start is not None:
        lines.append(f"start={start}")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _spawn_bash_background(command: str) -> tuple[subprocess.Popen, int]:
    """Launch a background bash process and return (Popen, msys_pid).

    The watcher's `kill -0` / `/proc` probes run inside Git Bash's MSYS
    runtime, which has its OWN pid namespace distinct from the raw Windows
    PID `subprocess.Popen.pid` reports (empirically verified: a Windows PID
    from `subprocess.Popen(['sleep', ...])` is NOT recognized by `kill -0`
    inside a separate bash invocation -- `kill: (<winpid>) - No such
    process` even while the process is alive). Spawning via
    `bash -c 'echo $$; ...'` and reading bash's own `$$` back is the only way
    to get a PID this watcher's probes will actually recognize -- exactly how
    invoke-codex-prompt.sh's own `$!` capture works.
    """
    bash = _bash()
    if not bash:
        pytest.skip("bash is unavailable")
    proc = subprocess.Popen(
        [bash, "-c", f"echo $$; {command}"],
        stdout=subprocess.PIPE,
        text=True,
    )
    msys_pid = int(proc.stdout.readline().strip())
    return proc, msys_pid


def test_dead_pid_with_no_completion_artifact_is_dead(tmp_path: Path) -> None:
    """The incident-shaped unit case: a launched run whose process dies
    leaving a zero-byte output artifact must be detected within one poll
    interval, not after the full --stall-secs/--max-secs window."""
    proc, msys_pid = _spawn_bash_background("sleep 30")
    proc.terminate()
    proc.wait(timeout=5)
    time.sleep(0.3)

    out = tmp_path / "dispatch.out"  # never written -- the run died silently
    pid_file = tmp_path / "dispatch.pid"
    _write_pid_file(pid_file, msys_pid)

    started = time.monotonic()
    line = _assert_one_line(
        _run_sh(
            "--out", _posix_path(out), "--pid-file", _posix_path(pid_file),
            "--poll-secs", "0.05", "--max-secs", "10", "--stall-secs", "2700",
        ),
        "DEAD pid-file=",
        expected_returncode=69,
    )
    elapsed = time.monotonic() - started
    assert line == f"DEAD pid-file={_posix_path(pid_file)}"
    # Detection must be near-instant relative to the 10s --max-secs this test
    # deliberately sets far above the expected detection latency -- proving
    # the watcher did not fall through to the old blind wait.
    assert elapsed < 5, f"DEAD took {elapsed}s -- should be near-instant"


def test_alive_pid_with_no_artifact_is_not_dead(tmp_path: Path) -> None:
    """Sanity check for the combined rule: a genuinely alive process with no
    artifact yet must NOT be reported dead -- it falls through to the
    pre-existing TIMEOUT path exactly as before this fix."""
    proc, msys_pid = _spawn_bash_background("sleep 30")
    try:
        out = tmp_path / "dispatch.out"
        pid_file = tmp_path / "dispatch.pid"
        _write_pid_file(pid_file, msys_pid)

        line = _assert_one_line(
            _run_sh(
                "--out", _posix_path(out), "--pid-file", _posix_path(pid_file),
                "--poll-secs", "0.05", "--max-secs", "1", "--stall-secs", "2700",
            ),
            "TIMEOUT max=",
            expected_returncode=124,
        )
        assert line == "TIMEOUT max=1"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_dead_pid_but_completion_artifact_present_is_still_done(tmp_path: Path) -> None:
    """Combined rule, the other direction (a finished-successfully run and a
    died-silently run are both 'not running' on their own): a confirmed-dead
    PID alongside a real completion signal is still DONE, never DEAD, because
    the DONE checks run first every poll."""
    proc, msys_pid = _spawn_bash_background("sleep 30")
    proc.terminate()
    proc.wait(timeout=5)
    time.sleep(0.3)

    out = tmp_path / "dispatch.out"
    out.write_text("GATE: PASS\n", encoding="ascii")
    pid_file = tmp_path / "dispatch.pid"
    _write_pid_file(pid_file, msys_pid)

    line = _assert_one_line(
        _run_sh(
            "--out", _posix_path(out), "--pid-file", _posix_path(pid_file),
            "--poll-secs", "0.05", "--max-secs", "2",
        ),
        "DONE out=",
    )
    assert line == f"DONE out={len(out.read_bytes())}"


def test_missing_pid_file_degrades_to_pre_fix_behavior(tmp_path: Path) -> None:
    """--pid-file pointing at a path that never gets created (an older
    invoke-*-prompt, a hand-rolled background launch, or any run started
    outside the wrapper -- the common case the live incident's own loop hit,
    not the edge) must behave IDENTICALLY to omitting the flag entirely: the
    watcher must still reach TIMEOUT, never DEAD."""
    out = tmp_path / "dispatch.out"
    pid_file = tmp_path / "never-created.pid"

    line = _assert_one_line(
        _run_sh(
            "--out", _posix_path(out), "--pid-file", _posix_path(pid_file),
            "--poll-secs", "0.05", "--max-secs", "1",
        ),
        "TIMEOUT max=",
        expected_returncode=124,
    )
    assert line == "TIMEOUT max=1"


def test_malformed_pid_file_degrades_to_pre_fix_behavior(tmp_path: Path) -> None:
    """A `.pid` file with no parseable `pid=` line degrades exactly like a
    missing one -- never treated as dead."""
    out = tmp_path / "dispatch.out"
    pid_file = tmp_path / "dispatch.pid"
    pid_file.write_text("not a pid file\n", encoding="ascii")

    line = _assert_one_line(
        _run_sh(
            "--out", _posix_path(out), "--pid-file", _posix_path(pid_file),
            "--poll-secs", "0.05", "--max-secs", "1",
        ),
        "TIMEOUT max=",
        expected_returncode=124,
    )
    assert line == "TIMEOUT max=1"


def test_recycled_pid_with_mismatched_start_marker_is_dead(tmp_path: Path) -> None:
    """PID-reuse hazard: a recorded PID that is CURRENTLY alive but whose
    start-time marker no longer matches (a DIFFERENT, later process now holds
    that PID) must be classified dead, not alive -- otherwise a recycled PID
    would mask a genuinely dead run indefinitely."""
    proc, msys_pid = _spawn_bash_background("sleep 30")
    try:
        out = tmp_path / "dispatch.out"
        pid_file = tmp_path / "dispatch.pid"
        # A real, currently-alive PID, but a start marker that cannot
        # possibly match it (an implausibly large tick count).
        _write_pid_file(pid_file, msys_pid, start="99999999999999999")

        line = _assert_one_line(
            _run_sh(
                "--out", _posix_path(out), "--pid-file", _posix_path(pid_file),
                "--poll-secs", "0.05", "--max-secs", "10", "--stall-secs", "2700",
            ),
            "DEAD pid-file=",
            expected_returncode=69,
        )
        assert line == f"DEAD pid-file={_posix_path(pid_file)}"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_incident_shaped_regression_invoke_and_watch_together(tmp_path: Path) -> None:
    """End-to-end incident replay: invoke-codex-prompt.sh launches a fake
    provider that hangs forever without ever writing lastmsg/out (the exact
    live-incident signature -- 8 of 16 provider runs producing zero-byte
    output), the provider is then killed directly (simulating whatever killed
    the real provider), and the watcher launched against the wrapper's own
    printed --pid-file must report DEAD within one poll cycle instead of
    silently waiting out the full stall/timeout window."""
    bash = _bash()
    if not bash:
        pytest.skip("bash is unavailable")

    fake = tmp_path / "fake-codex-hangs.sh"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "lastmsg=''\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  case \"$1\" in\n"
        "    --output-last-message) lastmsg=\"$2\"; shift 2 ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "cat >/dev/null\n"
        "sleep 300\n",  # never reaches the point of writing lastmsg/out
        encoding="ascii",
        newline="\n",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("incident replay\n", encoding="ascii")
    output_dir = tmp_path / "outputs"
    env = os.environ.copy()
    env["CODEX_BIN"] = _posix_path(fake)
    env["CODEX_PROMPTS_DIR"] = _posix_path(output_dir)

    wrapper_proc = subprocess.Popen(
        [bash, _posix_path(INVOKE_SH), "incident-replay", "--prompt-file", _posix_path(prompt)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        pid_file = None
        for _ in range(100):
            candidates = list(output_dir.glob("*.pid"))
            if candidates:
                pid_file = candidates[0]
                break
            time.sleep(0.1)
        assert pid_file is not None, "invoke-codex-prompt.sh never wrote a .pid file"

        recorded_pid = pid_file.read_text(encoding="ascii").splitlines()[0].split("=", 1)[1]
        out_file = next(output_dir.glob("*.out"))
        err_file = next(output_dir.glob("*.err"))
        lastmsg_file = output_dir / (pid_file.stem + ".lastmsg")

        # Kill the ACTUAL provider process the wrapper backgrounded -- not the
        # wrapper itself -- reproducing "the process died", not "the
        # orchestrator died". Uses bash's own `kill` (MSYS pid namespace, see
        # _spawn_bash_background) rather than Python's process APIs.
        subprocess.run([bash, "-c", f"kill -9 {recorded_pid}"], check=False)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            probe = subprocess.run([bash, "-c", f"kill -0 {recorded_pid} 2>/dev/null"])
            if probe.returncode != 0:
                break
            time.sleep(0.1)

        started = time.monotonic()
        watch = subprocess.run(
            [bash, _posix_path(WATCH_SH),
             "--out", _posix_path(out_file), "--err", _posix_path(err_file),
             "--lastmsg", _posix_path(lastmsg_file), "--pid-file", _posix_path(pid_file),
             "--poll-secs", "0.1", "--stall-secs", "2700", "--max-secs", "3600"],
            capture_output=True, text=True, timeout=15,
        )
        elapsed = time.monotonic() - started
        assert watch.returncode == 69, (watch.stdout, watch.stderr)
        assert watch.stdout.splitlines() == [f"DEAD pid-file={_posix_path(pid_file)}"]
        assert elapsed < 10, f"DEAD detection took {elapsed}s -- should be near-instant"
    finally:
        if wrapper_proc.poll() is None:
            wrapper_proc.terminate()
            try:
                wrapper_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                wrapper_proc.kill()
        try:
            wrapper_proc.communicate(timeout=5)
        except Exception:
            pass


def test_invoke_wrappers_write_pid_file_with_pid_line(tmp_path: Path) -> None:
    """Both invoke-*-prompt.sh wrappers must write a `.pid` sidecar carrying
    a parseable `pid=<integer>` first line -- the wire-level handoff the
    watcher's --pid-file probe depends on."""
    bash = _bash()
    if not bash:
        pytest.skip("bash is unavailable")

    cases = (
        (
            INVOKE_SH, "CODEX_BIN", "CODEX_PROMPTS_DIR",
            "#!/usr/bin/env bash\nlastmsg=''\n"
            "while [[ $# -gt 0 ]]; do case \"$1\" in "
            "--output-last-message) lastmsg=\"$2\"; shift 2 ;; *) shift ;; esac; done\n"
            "cat >/dev/null\nprintf 'GATE: PASS\\n' > \"$lastmsg\"\n",
            {},
        ),
        (
            CLAUDE_INVOKE_SH, "CLAUDE_BIN", "CLAUDE_PROMPTS_DIR",
            "#!/usr/bin/env bash\ncat >/dev/null\nprintf 'GATE: PASS\\n'\n",
            {"ANTHROPIC_API_KEY": "pid-file-wiring-test-key"},
        ),
    )
    for wrapper, bin_env, dir_env, fake_body, extra_env in cases:
        fake = tmp_path / f"fake-{wrapper.stem}.sh"
        fake.write_text(fake_body, encoding="ascii", newline="\n")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        prompt = tmp_path / f"prompt-{wrapper.stem}.md"
        prompt.write_text("pid-file wiring test\n", encoding="ascii")
        outdir = tmp_path / f"outputs-{wrapper.stem}"
        env = os.environ.copy()
        env[bin_env] = _posix_path(fake)
        env[dir_env] = _posix_path(outdir)
        env.update(extra_env)

        result = subprocess.run(
            [bash, _posix_path(wrapper), "pid-wiring-test", "--prompt-file", _posix_path(prompt)],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, result.stderr

        pid_files = list(outdir.glob("*.pid"))
        assert len(pid_files) == 1, (wrapper, result.stdout, result.stderr)
        first_line = pid_files[0].read_text(encoding="utf-8").splitlines()[0]
        assert first_line.split("=", 1)[0] == "pid"
        assert first_line.split("=", 1)[1].isdigit(), first_line


def test_powershell_dead_pid_with_no_completion_artifact_is_dead(tmp_path: Path) -> None:
    powershell = _powershell()
    if not powershell:
        pytest.skip("PowerShell is unavailable")

    proc = subprocess.Popen(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", "Start-Sleep -Seconds 30"]
    )
    win_pid = proc.pid
    proc.terminate()
    proc.wait(timeout=5)
    time.sleep(0.3)

    out = tmp_path / "dispatch.out"
    pid_file = tmp_path / "dispatch.pid"
    pid_file.write_text(f"pid={win_pid}\n", encoding="ascii")

    started = time.monotonic()
    result = _run_ps(
        "-Out", str(out), "-PidFile", str(pid_file),
        "-PollSecs", "0.1", "-MaxSecs", "10", "-StallSecs", "2700",
    )
    elapsed = time.monotonic() - started
    assert result.returncode == 69, result.stderr
    assert result.stdout.splitlines() == [f"DEAD pid-file={pid_file}"]
    assert elapsed < 5, f"DEAD took {elapsed}s -- should be near-instant"


def test_powershell_alive_pid_with_no_artifact_is_not_dead(tmp_path: Path) -> None:
    powershell = _powershell()
    if not powershell:
        pytest.skip("PowerShell is unavailable")

    proc = subprocess.Popen(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", "Start-Sleep -Seconds 30"]
    )
    try:
        out = tmp_path / "dispatch.out"
        pid_file = tmp_path / "dispatch.pid"
        pid_file.write_text(f"pid={proc.pid}\n", encoding="ascii")

        result = _run_ps(
            "-Out", str(out), "-PidFile", str(pid_file),
            "-PollSecs", "0.1", "-MaxSecs", "1", "-StallSecs", "2700",
        )
        assert result.returncode == 124, result.stderr
        assert result.stdout.splitlines() == ["TIMEOUT max=1"]
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_powershell_missing_pid_file_degrades_to_pre_fix_behavior(tmp_path: Path) -> None:
    if not _powershell():
        pytest.skip("PowerShell is unavailable")

    out = tmp_path / "dispatch.out"
    pid_file = tmp_path / "never-created.pid"

    result = _run_ps(
        "-Out", str(out), "-PidFile", str(pid_file),
        "-PollSecs", "0.1", "-MaxSecs", "1",
    )
    assert result.returncode == 124, result.stderr
    assert result.stdout.splitlines() == ["TIMEOUT max=1"]


def test_powershell_recycled_pid_with_mismatched_start_marker_is_dead(tmp_path: Path) -> None:
    powershell = _powershell()
    if not powershell:
        pytest.skip("PowerShell is unavailable")

    proc = subprocess.Popen(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", "Start-Sleep -Seconds 30"]
    )
    try:
        out = tmp_path / "dispatch.out"
        pid_file = tmp_path / "dispatch.pid"
        pid_file.write_text(f"pid={proc.pid}\nstart=99999999999999999\n", encoding="ascii")

        result = _run_ps(
            "-Out", str(out), "-PidFile", str(pid_file),
            "-PollSecs", "0.1", "-MaxSecs", "10", "-StallSecs", "2700",
        )
        assert result.returncode == 69, result.stderr
        assert result.stdout.splitlines() == [f"DEAD pid-file={pid_file}"]
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_invoke_ps1_wrappers_write_pid_file_with_pid_line(tmp_path: Path) -> None:
    """Both invoke-*-prompt.ps1 wrappers must write a `.pid` sidecar carrying
    a parseable `pid=<integer>` first line, mirroring the Bash sibling."""
    powershell = _powershell()
    if not powershell:
        pytest.skip("PowerShell is unavailable")

    codex_fake = tmp_path / "fake-codex.ps1"
    codex_fake.write_text(
        "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)\n"
        "$lastmsg = ''\n"
        "for ($i = 0; $i -lt $Arguments.Count; $i++) {\n"
        "  if ($Arguments[$i] -eq '--output-last-message') { $lastmsg = $Arguments[$i + 1] }\n"
        "}\n"
        "if (-not $lastmsg) { exit 97 }\n"
        "$input | Out-Null\n"
        "[System.IO.File]::WriteAllText($lastmsg, \"GATE: PASS`n\", [System.Text.UTF8Encoding]::new($false))\n"
        "exit 0\n",
        encoding="utf-8", newline="\n",
    )
    claude_fake = tmp_path / "fake-claude.ps1"
    claude_fake.write_text(
        "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)\n"
        "$input | Out-Null\n"
        "Write-Output 'GATE: PASS'\n"
        "exit 0\n",
        encoding="utf-8", newline="\n",
    )

    cases = (
        (INVOKE_PS1, "CODEX_BIN", "CODEX_PROMPTS_DIR", codex_fake, {}),
        (CLAUDE_INVOKE_PS1, "CLAUDE_BIN", "CLAUDE_PROMPTS_DIR", claude_fake,
         {"ANTHROPIC_API_KEY": "pid-file-wiring-test-key"}),
    )
    for wrapper, bin_env, dir_env, fake, extra_env in cases:
        prompt = tmp_path / f"prompt-{wrapper.stem}.md"
        prompt.write_text("pid-file wiring test\n", encoding="utf-8")
        outdir = tmp_path / f"outputs-{wrapper.stem}"
        env = os.environ.copy()
        env[bin_env] = str(fake)
        env[dir_env] = str(outdir)
        env.update(extra_env)

        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(wrapper), "pid-wiring-test", "-PromptFile", str(prompt)],
            cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, result.stderr

        pid_files = list(outdir.glob("*.pid"))
        assert len(pid_files) == 1, (wrapper, result.stdout, result.stderr)
        first_line = pid_files[0].read_text(encoding="utf-8").splitlines()[0]
        assert first_line.split("=", 1)[0] == "pid"
        assert first_line.split("=", 1)[1].isdigit(), first_line
