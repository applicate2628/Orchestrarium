"""Terminal-matrix tests for the Python dispatch watcher and prompt owners."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from tests.fixtures.codex_hook_fixture import (
    FAKE_CODEX_HOOKS_HOST,
    prepare_codex_home,
)
from tests.fixtures.provider_prompt_projection import (
    materialize_provider_prompt_runtime,
)


ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "src.claude/agents/scripts/await-codex-dispatch.py"
CODEX = ROOT / "src.claude/agents/scripts/invoke-codex-prompt.py"
CLAUDE = ROOT / "src.claude/agents/scripts/invoke-claude-prompt.py"


def _watch(tmp_path: Path, *extra: str):
    out = tmp_path / "run.out"
    err = tmp_path / "run.err"
    return subprocess.run(
        [
            sys.executable,
            str(WATCH),
            "--out",
            str(out),
            "--err",
            str(err),
            "--poll-secs",
            "0",
            "--max-secs",
            "0",
            *extra,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )


def test_nonempty_out_is_done(tmp_path: Path) -> None:
    (tmp_path / "run.out").write_text("delivered\n", encoding="utf-8")
    result = _watch(tmp_path)
    assert result.returncode == 0
    assert result.stdout.startswith("DONE ")


def test_nonempty_lastmsg_is_done(tmp_path: Path) -> None:
    lastmsg = tmp_path / "run.lastmsg"
    lastmsg.write_text("GATE: PASS\n", encoding="utf-8")
    result = _watch(tmp_path, "--lastmsg", str(lastmsg))
    assert result.returncode == 0
    assert result.stdout == f"DONE lastmsg={lastmsg.stat().st_size}\n"


def test_commit_base_change_is_done(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    state = tmp_path / "state.txt"
    state.write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "state.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=watcher-test",
            "-c",
            "user.email=watcher@test.invalid",
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )
    base = subprocess.check_output(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True
    ).strip()
    process = subprocess.Popen(
        [
            sys.executable,
            str(WATCH),
            "--out",
            str(tmp_path / "run.out"),
            "--commit-base",
            base,
            "--poll-secs",
            "0.05",
            "--max-secs",
            "4",
        ],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    time.sleep(0.2)
    state.write_text("changed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "state.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=watcher-test",
            "-c",
            "user.email=watcher@test.invalid",
            "commit",
            "-qm",
            "changed",
        ],
        check=True,
    )
    stdout, stderr = process.communicate(timeout=10)
    assert process.returncode == 0, stderr
    head = subprocess.check_output(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True
    ).strip()
    assert stdout == f"DONE committed={head}\n"


def test_timeout_is_124(tmp_path: Path) -> None:
    result = _watch(tmp_path)
    assert result.returncode == 124
    assert result.stdout.startswith("TIMEOUT ")


def test_idle_err_is_stall_75(tmp_path: Path) -> None:
    err = tmp_path / "run.err"
    err.write_text("progress\n", encoding="utf-8")
    old = time.time() - 60
    os.utime(err, (old, old))
    result = _watch(tmp_path, "--stall-secs", "1")
    assert result.returncode == 75
    assert result.stdout.startswith("STALL ")


def test_content_filter_is_77(tmp_path: Path) -> None:
    (tmp_path / "run.err").write_text(
        "Request was flagged by the cybersecurity content filter.\n",
        encoding="utf-8",
    )
    result = _watch(tmp_path)
    assert result.returncode == 77
    assert result.stdout.startswith("FILTERED ")


def test_reworded_content_filter_is_77(tmp_path: Path) -> None:
    (tmp_path / "run.err").write_text(
        "NOTICE: this request was flagged as a possible Cybersecurity concern.\n",
        encoding="utf-8",
    )
    result = _watch(tmp_path)
    assert result.returncode == 77


def test_filter_marker_outside_tail_window_does_not_misfire(tmp_path: Path) -> None:
    (tmp_path / "run.err").write_text(
        "ERROR: This content was flagged for possible cybersecurity risk.\n"
        + ("still working normally\n" * 600),
        encoding="utf-8",
    )
    result = _watch(tmp_path)
    assert result.returncode == 124


def test_completion_artifact_wins_over_filter_marker(tmp_path: Path) -> None:
    (tmp_path / "run.out").write_text("GATE: PASS\n", encoding="utf-8")
    (tmp_path / "run.err").write_text(
        "ERROR: This content was flagged for possible cybersecurity risk.\n",
        encoding="utf-8",
    )
    result = _watch(tmp_path)
    assert result.returncode == 0
    assert result.stdout.startswith("DONE out=")


def test_dead_pid_is_69_but_completion_wins(tmp_path: Path) -> None:
    pid_file = tmp_path / "run.pid"
    pid_file.write_text("pid=99999999\n", encoding="utf-8")
    result = _watch(tmp_path, "--pid-file", str(pid_file))
    assert result.returncode == 69
    (tmp_path / "run.out").write_text("delivered\n", encoding="utf-8")
    result = _watch(tmp_path, "--pid-file", str(pid_file))
    assert result.returncode == 0


def test_missing_and_malformed_pid_degrade_to_timeout(tmp_path: Path) -> None:
    for pid_file in (tmp_path / "missing.pid", tmp_path / "bad.pid"):
        if pid_file.name == "bad.pid":
            pid_file.write_text("not-a-pid\n", encoding="utf-8")
        result = _watch(tmp_path, "--pid-file", str(pid_file))
        assert result.returncode == 124


def test_healthy_slow_run_with_no_marker_still_polls(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"]
    )
    try:
        (tmp_path / "run.err").write_text(
            "provider started\nstill working\n", encoding="utf-8"
        )
        (tmp_path / "run.pid").write_text(
            f"pid={process.pid}\n", encoding="utf-8"
        )
        result = _watch(
            tmp_path,
            "--pid-file",
            str(tmp_path / "run.pid"),
            "--stall-secs",
            "2700",
            "--max-secs",
            "1",
            "--poll-secs",
            "0.05",
        )
        assert result.returncode == 124, result.stdout
        assert result.stdout == "TIMEOUT max=1\n"
    finally:
        process.terminate()
        process.wait(timeout=5)


def test_recycled_pid_with_mismatched_start_marker_is_dead(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"]
    )
    try:
        (tmp_path / "run.pid").write_text(
            f"pid={process.pid}\nstart=definitely-not-this-process\n",
            encoding="utf-8",
        )
        result = _watch(
            tmp_path,
            "--pid-file",
            str(tmp_path / "run.pid"),
            "--max-secs",
            "10",
        )
        assert result.returncode == 69, result.stdout
        assert result.stdout == f"DEAD pid-file={tmp_path / 'run.pid'}\n"
    finally:
        process.terminate()
        process.wait(timeout=5)


@pytest.mark.parametrize(
    ("provider", "entrypoint", "bin_env", "output_env"),
    (
        ("codex", CODEX, "CODEX_BIN", "CODEX_PROMPTS_DIR"),
        ("claude", CLAUDE, "CLAUDE_BIN", "CLAUDE_PROMPTS_DIR"),
    ),
)
def test_python_prompt_owner_returns_complete_result_and_reclaims_artifacts(
    tmp_path: Path,
    provider: str,
    entrypoint: Path,
    bin_env: str,
    output_env: str,
) -> None:
    projection = tmp_path / f"{provider}-projection" / "agents" / "scripts"
    projection.mkdir(parents=True)
    projected_entrypoint = projection / entrypoint.name
    shutil.copyfile(entrypoint, projected_entrypoint)
    materialize_provider_prompt_runtime(ROOT, projection)
    projection_shared = projection.parents[1] / "shared"
    projection_shared.mkdir()
    shutil.copyfile(
        ROOT / "shared" / "provider-prompt-projections.v1.json",
        projection_shared / "provider-prompt-projections.v1.json",
    )
    shutil.copyfile(
        ROOT / "shared" / "external-prompt-governance.md",
        projection / "external-prompt-governance.md",
    )
    shutil.copyfile(
        ROOT / "shared" / "external-role-taxonomy.v1.json",
        projection / "external-role-taxonomy.v1.json",
    )
    env_capture = tmp_path / f"{provider}.env"
    fake = tmp_path / f"fake-{provider}.py"
    fake.write_text(
        "import json,os,pathlib,runpy,sys\n"
        "args=sys.argv[1:]\n"
        "if 'app-server' in args:\n"
        f"    runpy.run_path({str(FAKE_CODEX_HOOKS_HOST)!r}, run_name='__main__')\n"
        f"pathlib.Path({str(env_capture)!r}).write_text("
        "os.environ.get('ORCHESTRARIUM_DISPATCHED_REVIEW', ''), encoding='utf-8')\n"
        + (
            "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'GATE: PASS\\n'}}))\n"
            if provider == "codex"
            else "print('GATE: PASS')\n"
        ),
        encoding="utf-8",
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_text("review this\n", encoding="utf-8")
    env = os.environ.copy()
    env[bin_env] = str(fake)
    env[output_env] = str(tmp_path / f"{provider}-artifacts")
    if provider == "codex":
        env["CODEX_HOME"] = str(prepare_codex_home(tmp_path))
        env["OPENAI_API_KEY"] = "fake-commercial-credential"
        helper = Path(env["CODEX_HOME"]) / "skills" / "lead" / "scripts" / "check-hook-health.py"
        helper.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / "scripts" / helper.name, helper)
    if provider == "claude":
        env["ANTHROPIC_API_KEY"] = "fake-commercial-credential"
    result = subprocess.run(
        [
            sys.executable,
            str(projected_entrypoint),
            "watch-test",
            "--prompt-file",
            str(prompt),
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == 1
    prefix = "ORCHESTRARIUM_PROVIDER_RESULT_V2="
    assert lines[0].startswith(prefix)
    payload = json.loads(lines[0][len(prefix) :])
    assert payload["schema"] == "orchestrarium.provider-result.v2"
    assert payload["resultText"].replace("\r\n", "\n") == "GATE: PASS\n"
    assert payload["exitCode"] == 0
    assert payload["token"] == "COMPLETE:EXTERNAL_NONAUTHORIZING"
    assert payload["primaryOutcome"]["token"] == "COMPLETE:PASS"
    assert payload["authorizing"] is False
    assert payload["closesRunIds"] == []
    assert payload["status"] == "completed"
    assert payload["gate"] == "PASS"
    assert payload["cancelled"] is False
    assert payload["timedOut"] is False
    assert payload["stderrMarkerCount"] == 0
    assert list((tmp_path / f"{provider}-artifacts").iterdir()) == []
    assert env_capture.read_text(encoding="utf-8") == (
        "1" if provider == "claude" else ""
    )


def test_terminal_exit_codes_are_distinct() -> None:
    assert len({0, 69, 75, 77, 124, 2}) == 6


def test_usage_errors_are_stderr_and_retired_aliases_reach_python_owner(
    tmp_path: Path,
) -> None:
    missing = subprocess.run(
        [sys.executable, str(WATCH), "-PollSecs", "0"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert missing.returncode == 2
    assert missing.stdout == ""
    assert "required" in missing.stderr

    out = tmp_path / "run.out"
    out.write_text("done\n", encoding="utf-8")
    alias = subprocess.run(
        [
            sys.executable,
            str(WATCH),
            "-Out",
            str(out),
            "-PollSecs",
            "0",
            "-MaxSecs",
            "0",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert alias.returncode == 0
    assert alias.stdout == f"DONE out={out.stat().st_size}\n"
