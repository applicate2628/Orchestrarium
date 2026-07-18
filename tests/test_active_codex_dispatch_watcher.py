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


def _assert_one_line(result: subprocess.CompletedProcess[str], prefix: str) -> str:
    assert result.returncode == 0, result.stderr
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
    )
    assert int(line.split("=", 1)[1]) >= 1


def test_max_elapsed_is_timeout(tmp_path: Path) -> None:
    out = tmp_path / "dispatch.out"

    line = _assert_one_line(
        _run_sh(
            "--out", _posix_path(out), "--poll-secs", "0.05", "--max-secs", "1",
        ),
        "TIMEOUT max=",
    )
    assert line == "TIMEOUT max=1"


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
    assert line.returncode == 0, line.stderr
    assert line.stdout.startswith("STALL err-idle=")

    line = _run_ps(
        "-Out", str(tmp_path / "missing.out"), "-PollSecs", "0.05", "-MaxSecs", "1",
    )
    assert line.returncode == 0, line.stderr
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
    assert "--out" in shell and "--err" in shell and "--lastmsg" in shell
    assert "--stall-secs 2700" in shell

    assert note in powershell
    assert powershell.index("Write-Output $lastmsgPath") < powershell.index(note)
    assert powershell.index("Write-Output $promptPath") < powershell.index("$promptBody | & $codexPath exec")
    assert "await-codex-dispatch.ps1" in powershell
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
    assert command.startswith("bash .claude/agents/scripts/await-codex-dispatch.sh")
    assert f"--out {shlex.quote(lines[1])}" in command
    assert f"--err {shlex.quote(lines[2])}" in command
    assert f"--lastmsg {shlex.quote(lines[3])}" in command


def test_powershell_watcher_port_names_required_primitives() -> None:
    source = WATCH_PS1.read_text(encoding="utf-8")
    assert "Get-Date" in source
    assert "Test-Path" in source
    assert "LastWriteTime" in source
    assert "Write-Output" in source
