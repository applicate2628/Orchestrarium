"""Completion-oracle tests for the shared Python provider prompt owner."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src.claude/agents/scripts/provider_prompt.py"
INSTALLER_MODULE = ROOT / "scripts/production_installer.py"
ENTRYPOINTS = {
    "codex": ROOT / "src.claude/agents/scripts/invoke-codex-prompt.py",
    "claude": ROOT / "src.claude/agents/scripts/invoke-claude-prompt.py",
}
BIN_ENV = {"codex": "CODEX_BIN", "claude": "CLAUDE_BIN"}
OUTPUT_ENV = {"codex": "CODEX_PROMPTS_DIR", "claude": "CLAUDE_PROMPTS_DIR"}
spec = importlib.util.spec_from_file_location("provider_prompt_oracle_test", MODULE)
assert spec and spec.loader
owner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner
spec.loader.exec_module(owner)
installer_spec = importlib.util.spec_from_file_location(
    "production_installer_oracle_test", INSTALLER_MODULE
)
assert installer_spec and installer_spec.loader
installer = importlib.util.module_from_spec(installer_spec)
sys.modules[installer_spec.name] = installer
installer_spec.loader.exec_module(installer)


def _make_work_item(tmp_path: Path, suffix: str) -> Path:
    item = tmp_path / "work-items" / "active" / f"2026-01-01-{suffix}"
    item.mkdir(parents=True)
    (item / "design.md").write_text("fixture artifact\n", encoding="utf-8")
    (item / "status.md").write_text(
        "# Status\n\n- state: open\n\n"
        "## Current state\n\nFixture item.\n\n"
        "## Active agents\n\n- none\n\n"
        "## Completed agents\n\n- none\n\n"
        "## Next action\n\n- none\n",
        encoding="utf-8",
    )
    return item


def _make_fake_provider(
    tmp_path: Path,
    provider: str,
    *,
    exit_code: int = 0,
    write_lastmsg: bool = True,
) -> Path:
    fake = tmp_path / f"fake-{provider}.py"
    fake.write_text(
        "import json,os,pathlib,sys\n"
        "args=sys.argv[1:]\n"
        "if 'app-server' in args:\n"
        "    config_path=pathlib.Path(os.environ['CODEX_HOME'])/'hooks.json'\n"
        "    config=json.loads(config_path.read_text(encoding='utf-8'))\n"
        "    records=[]\n"
        "    for event,entries in config['hooks'].items():\n"
        "        for entry in entries:\n"
        "            for hook in entry['hooks']:\n"
        "                records.append({'eventName':event,'matcher':entry.get('matcher'),"
        "'handlerType':'command','command':hook['command'],'sourcePath':str(config_path.resolve()),"
        "'enabled':True,'trustStatus':'trusted','currentHash':'sha256:fixture'})\n"
        "    for line in sys.stdin:\n"
        "        message=json.loads(line)\n"
        "        if message.get('id') == 1:\n"
        "            print(json.dumps({'id':1,'result':{}}), flush=True)\n"
        "        elif message.get('id') == 2:\n"
        "            print(json.dumps({'id':2,'result':{'data':[{'hooks':records}]}}), flush=True)\n"
        "    raise SystemExit(0)\n"
        "sys.stdin.buffer.read()\n"
        + (
            "if '--output-last-message' in args:\n"
            "    path=pathlib.Path(args[args.index('--output-last-message')+1])\n"
            + (
                "    path.write_text('GATE: PASS\\n', encoding='utf-8')\n"
                if write_lastmsg
                else "    pass\n"
            )
            if provider == "codex"
            else ""
        )
        + f"raise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    return fake


def _prepare_codex_home(tmp_path: Path) -> Path:
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    hooks: dict[str, list[dict]] = {}
    installed_root = ROOT / "src.codex" / "skills" / "lead"
    for _marker, script, event, matcher in installer._hook_specs("codex", installed_root):
        entry = {"hooks": [{"type": "command", "command": f"{sys.executable} {script}"}]}
        if matcher is not None:
            entry["matcher"] = matcher
        hooks.setdefault(event, []).append(entry)
    (codex_home / "hooks.json").write_text(
        json.dumps({"hooks": hooks}), encoding="utf-8"
    )
    return codex_home


def _run_transport(
    tmp_path: Path,
    provider: str,
    *,
    exit_code: int = 0,
    write_lastmsg: bool = True,
    with_ledger: bool = True,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    fake = _make_fake_provider(
        tmp_path,
        provider,
        exit_code=exit_code,
        write_lastmsg=write_lastmsg,
    )
    item = _make_work_item(tmp_path, f"oracle-{provider}-{exit_code}-{write_lastmsg}")
    prompt = tmp_path / f"{provider}.md"
    prompt.write_text("fixture prompt\n", encoding="utf-8")
    env = os.environ.copy()
    env[BIN_ENV[provider]] = str(fake)
    env[OUTPUT_ENV[provider]] = str(tmp_path / f"{provider}-outputs")
    if provider == "codex":
        env["CODEX_HOME"] = str(_prepare_codex_home(tmp_path))
    if provider == "claude":
        env["ANTHROPIC_API_KEY"] = "fake-commercial-credential"
    arguments = [
        sys.executable,
        str(ENTRYPOINTS[provider]),
        "oracle-fixture",
        "--prompt-file",
        str(prompt),
    ]
    if with_ledger:
        arguments += [
            "--ledger",
            str(item),
            "--ledger-role",
            "architecture-reviewer",
            "--ledger-lane",
            "fixture-lane",
            "--ledger-artifact",
            "design.md",
        ]
    result = subprocess.run(
        arguments,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    return result, item


def _ledger_events(item: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (item / "agent-runs.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def _make_ledger_probe(helper: Path, marker: Path, label: str) -> None:
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text(
        "from pathlib import Path\n"
        f"with Path({str(marker)!r}).open('a', encoding='utf-8') as stream:\n"
        f"    stream.write({label!r} + '\\n')\n",
        encoding="utf-8",
    )


def _run_installed_transport(
    tmp_path: Path,
    provider: str,
    available: tuple[str, ...],
) -> tuple[subprocess.CompletedProcess[str], dict[str, Path]]:
    script_dir = tmp_path / "target" / "agents" / "scripts"
    script_dir.mkdir(parents=True)
    for source in (MODULE, ENTRYPOINTS[provider]):
        shutil.copy2(source, script_dir / source.name)

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    candidates = {
        "sibling": script_dir / "agent-run-ledger.py",
        "cwd": cwd / "scripts" / "agent-run-ledger.py",
        "repository": script_dir.parents[2] / "scripts" / "agent-run-ledger.py",
    }
    markers = {label: tmp_path / f"{label}.marker" for label in candidates}
    for label in available:
        _make_ledger_probe(candidates[label], markers[label], label)

    fake = _make_fake_provider(tmp_path, provider)
    prompt = tmp_path / "installed.md"
    prompt.write_text("installed fixture\n", encoding="utf-8")
    env = os.environ.copy()
    env[BIN_ENV[provider]] = str(fake)
    env[OUTPUT_ENV[provider]] = str(tmp_path / "installed-outputs")
    if provider == "claude":
        env["ANTHROPIC_API_KEY"] = "fake-commercial-credential"
    result = subprocess.run(
        [
            sys.executable,
            str(script_dir / ENTRYPOINTS[provider].name),
            "installed-ledger-probe",
            "--prompt-file",
            str(prompt),
            "--ledger",
            str(tmp_path / "dummy-item"),
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    return result, markers


@pytest.mark.parametrize(
    ("line", "expected"),
    (
        ("ERROR: failed", 1),
        ("FATAL: failed", 1),
        ("API Error: failed", 1),
        ("2026-07-30T10:11:12Z ERROR: failed", 1),
        ("prose mentions ERROR: but is not anchored", 0),
        ("GATE: PASS", 0),
    ),
)
def test_error_marker_is_anchored(tmp_path: Path, line: str, expected: int) -> None:
    path = tmp_path / "run.err"
    path.write_text(line + "\n", encoding="utf-8")
    assert owner.has_error_markers(path) == expected


@pytest.mark.parametrize(
    ("exit_code", "out", "err", "lastmsg", "status", "gate", "note", "token"),
    (
        (1, "GATE: PASS\n", "", "", "blocked", "none", "nonzero exit", "FAILED:nonzero-exit"),
        (0, "", "", "", "blocked", "none", "empty .out", "UNVERIFIED:empty"),
        (0, "GATE: PASS\n", "ERROR: failed\n", "", "blocked", "none", "err markers", "UNVERIFIED:err-markers"),
        (0, "GATE: PASS\n", "", "", "completed", "PASS", "final-line GATE: PASS", "COMPLETE:PASS"),
        (0, "GATE: REVISE\n", "", "", "revise", "REVISE", "final-line GATE: REVISE", "COMPLETE:REVISE"),
        (0, "analysis only\n", "", "", "blocked", "none", "not an anchored", "UNVERIFIED:no-gate-line"),
        (0, "analysis only\n", "", "GATE: PASS\n", "completed", "PASS", "final-line GATE: PASS", "COMPLETE:PASS"),
    ),
)
def test_terminal_oracle_records_exact_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
    out: str,
    err: str,
    lastmsg: str,
    status: str,
    gate: str,
    note: str,
    token: str,
) -> None:
    out_path = tmp_path / "run.out"
    err_path = tmp_path / "run.err"
    lastmsg_path = tmp_path / "run.lastmsg"
    out_path.write_text(out, encoding="utf-8")
    err_path.write_text(err, encoding="utf-8")
    if lastmsg:
        lastmsg_path.write_text(lastmsg, encoding="utf-8")
    captured: list[list[str]] = []
    monkeypatch.setattr(owner, "run_ledger", lambda args: captured.append(args) or True)
    control = owner.Control(ledger="item")
    terminal = owner.evaluate_terminal(exit_code, out_path, err_path, lastmsg_path)
    owner.record_terminal(
        control,
        "codex",
        "gpt-5.6-sol",
        "xhigh",
        "slug",
        "launch-id",
        terminal,
    )
    args = captured[0]
    assert terminal.token == token
    assert args[args.index("--status") + 1] == status
    assert args[args.index("--gate") + 1] == gate
    assert note in args[args.index("--notes") + 1]


def test_verdict_writer_atomically_replaces_one_token(tmp_path: Path) -> None:
    verdict = tmp_path / "run.verdict"
    owner.write_verdict(verdict, "LAUNCHED")
    owner.write_verdict(verdict, "COMPLETE:PASS")
    assert verdict.read_bytes() == b"COMPLETE:PASS\n"
    assert not list(tmp_path.glob(".run.verdict.*.tmp"))


@pytest.mark.parametrize("provider", ("codex", "claude"))
@pytest.mark.parametrize("provider_exit", (0, 7))
def test_ledgered_and_unledgered_runs_share_terminal_verdict(
    tmp_path: Path, provider: str, provider_exit: int
) -> None:
    observed: list[str] = []
    for label, with_ledger in (("ledgered", True), ("unledgered", False)):
        case = tmp_path / label
        case.mkdir()
        result, item = _run_transport(
            case,
            provider,
            exit_code=provider_exit,
            with_ledger=with_ledger,
        )
        assert result.returncode == provider_exit, result.stderr
        verdicts = list((case / f"{provider}-outputs").glob("*.verdict"))
        assert len(verdicts) == 1
        observed.append(verdicts[0].read_text(encoding="ascii"))
        assert (item / "agent-runs.jsonl").exists() is with_ledger
    expected = (
        "FAILED:nonzero-exit\n"
        if provider_exit
        else "COMPLETE:PASS\n"
        if provider == "codex"
        else "UNVERIFIED:empty\n"
    )
    assert observed == [expected, expected]


def test_installed_python_layout_uses_sibling_ledger_helper(tmp_path: Path) -> None:
    result, markers = _run_installed_transport(
        tmp_path, "claude", ("sibling",)
    )
    assert result.returncode == 0, result.stderr
    assert markers["sibling"].read_text(encoding="utf-8").splitlines() == [
        "sibling",
        "sibling",
    ]


@pytest.mark.parametrize(
    ("available", "expected"),
    (
        (("sibling", "cwd", "repository"), "sibling"),
        (("cwd", "repository"), "cwd"),
        (("repository",), "repository"),
    ),
)
def test_ledger_helper_resolution_prefers_sibling_and_preserves_fallbacks(
    tmp_path: Path,
    available: tuple[str, ...],
    expected: str,
) -> None:
    result, markers = _run_installed_transport(tmp_path, "claude", available)
    assert result.returncode == 0, result.stderr
    assert markers[expected].read_text(encoding="utf-8").splitlines() == [
        expected,
        expected,
    ]
    for label, marker in markers.items():
        if label != expected:
            assert not marker.exists(), f"unexpected helper selected: {label}"


@pytest.mark.parametrize("provider", ("codex", "claude"))
@pytest.mark.parametrize("provider_exit", (1, 0))
def test_empty_trace_still_settles_terminal(
    tmp_path: Path, provider: str, provider_exit: int
) -> None:
    result, item = _run_transport(
        tmp_path, provider, exit_code=provider_exit
    )
    assert result.returncode == provider_exit, result.stderr
    events = _ledger_events(item)
    launches = [event for event in events if event.get("eventKind") == "launch"]
    terminals = [
        event for event in events if event.get("eventKind") == "terminal"
    ]
    assert len(launches) == 1
    assert len(terminals) == 1
    terminal = terminals[0]
    assert terminal["launchRunId"] == launches[0]["runId"]
    codex_success = provider == "codex" and provider_exit == 0
    assert terminal["status"] == ("completed" if codex_success else "blocked")
    assert terminal["gate"] == ("PASS" if codex_success else "none")
    expected_note = (
        "nonzero exit"
        if provider_exit
        else "final-line GATE: PASS"
        if codex_success
        else "empty .out"
    )
    assert expected_note in terminal["notes"]


def test_codex_empty_lastmsg_and_out_exit_zero_records_blocked_terminal(
    tmp_path: Path,
) -> None:
    result, item = _run_transport(
        tmp_path, "codex", exit_code=0, write_lastmsg=False
    )
    assert result.returncode == 0, result.stderr
    terminal = next(
        event
        for event in _ledger_events(item)
        if event.get("eventKind") == "terminal"
    )
    assert terminal["status"] == "blocked"
    assert terminal["gate"] == "none"
    assert "empty .out" in terminal["notes"]


def test_provider_prompt_codex_require_preflight_blocks_popen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fixture prompt\n", encoding="utf-8")
    monkeypatch.setenv("CODEX_PROMPTS_DIR", str(tmp_path / "outputs"))
    fake_codex = tmp_path / "codex.exe"
    fake_codex.write_bytes(b"fixture")
    monkeypatch.setattr(owner, "resolve_provider_command", lambda _provider: [str(fake_codex)])
    monkeypatch.setattr(owner, "require_codex_hook_trust", lambda *_args: 23)
    monkeypatch.setattr(
        owner,
        "prompt_bytes",
        lambda _control: (_ for _ in ()).throw(AssertionError("prompt must not be read")),
    )
    called = False

    def forbidden_popen(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("Codex subprocess must not start after require failure")

    monkeypatch.setattr(owner.subprocess, "Popen", forbidden_popen)
    result = owner.launch(
        "codex",
        [
            "trust-gate",
            "--prompt-file",
            str(prompt),
            "--ledger",
            str(tmp_path / "work-items" / "active" / "trust-denied"),
            "--",
            "--model",
            "gpt-5.6-sol",
            "-c",
            "model_reasoning_effort=xhigh",
        ],
    )
    assert result == 23
    assert not called
    assert not (tmp_path / "outputs").exists()
    assert not (tmp_path / "work-items").exists()


def test_codex_hook_trust_uses_effective_codex_home_not_claude_adjacent_helper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    claude_scripts = tmp_path / "claude" / "agents" / "scripts"
    claude_scripts.mkdir(parents=True)
    claude_adjacent = claude_scripts / "check-hook-health.py"
    claude_adjacent.write_text("wrong inventory\n", encoding="utf-8")
    provider_copy = claude_scripts / "provider_prompt.py"
    provider_copy.write_text("fixture\n", encoding="utf-8")
    codex_home = tmp_path / "codex-home"
    codex_helper = codex_home / "skills" / "lead" / "scripts" / "check-hook-health.py"
    codex_helper.parent.mkdir(parents=True)
    codex_helper.write_text("right inventory\n", encoding="utf-8")
    monkeypatch.setattr(owner, "__file__", str(provider_copy))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    assert owner.codex_hook_health_helper(codex_home) == codex_helper
    invoked: list[str] = []

    def trusted_require(command, **_kwargs):
        invoked.extend(command)
        return subprocess.CompletedProcess(command, 0, "PASS\n", "")

    monkeypatch.setattr(owner.subprocess, "run", trusted_require)
    codex_binary = tmp_path / "codex.exe"
    codex_binary.write_bytes(b"fixture")
    assert owner.require_codex_hook_trust(
        [str(codex_binary)], codex_home, tmp_path
    ) == 0
    assert str(codex_helper) in invoked
    assert str(claude_adjacent) not in invoked
    assert str(codex_home / "hooks.json") in invoked


def test_admitted_launch_settles_terminal_when_popen_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fixture\n", encoding="utf-8")
    fake_codex = tmp_path / "codex.exe"
    fake_codex.write_bytes(b"fixture")
    monkeypatch.setenv("CODEX_PROMPTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(owner, "resolve_provider_command", lambda _provider: [str(fake_codex)])
    monkeypatch.setattr(owner, "require_codex_hook_trust", lambda *_args: 0)
    monkeypatch.setattr(owner, "ledger_helper", lambda: tmp_path / "ledger.py")
    ledger_calls: list[list[str]] = []
    monkeypatch.setattr(owner, "run_ledger", lambda args: ledger_calls.append(args) or True)
    terminal_calls: list[tuple] = []
    monkeypatch.setattr(owner, "record_terminal", lambda *args: terminal_calls.append(args))
    monkeypatch.setattr(
        owner.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("fixture launch failure")),
    )
    result = owner.launch(
        "codex",
        ["popen-failure", "--prompt-file", str(prompt), "--ledger", str(tmp_path / "item")],
    )
    assert result == 1
    assert len(ledger_calls) == 1
    assert len(terminal_calls) == 1
    verdicts = list((tmp_path / "outputs").glob("*.verdict"))
    assert len(verdicts) == 1
    assert verdicts[0].read_text(encoding="ascii") == "FAILED:nonzero-exit\n"


def test_initial_verdict_failure_prevents_provider_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fixture\n", encoding="utf-8")
    fake_codex = tmp_path / "codex.exe"
    fake_codex.write_bytes(b"fixture")
    monkeypatch.setenv("CODEX_PROMPTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(owner, "resolve_provider_command", lambda _provider: [str(fake_codex)])
    monkeypatch.setattr(owner, "require_codex_hook_trust", lambda *_args: 0)
    monkeypatch.setattr(
        owner,
        "write_verdict",
        lambda *_args: (_ for _ in ()).throw(OSError("fixture verdict denial")),
    )

    def forbidden_popen(*_args, **_kwargs):
        raise AssertionError("provider must not start without a LAUNCHED verdict")

    monkeypatch.setattr(owner.subprocess, "Popen", forbidden_popen)
    result = owner.launch("codex", ["verdict-denied", "--prompt-file", str(prompt)])
    assert result == 1
    assert "could not write launch verdict" in capsys.readouterr().err


def test_ledger_launch_failure_replaces_launched_verdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fixture\n", encoding="utf-8")
    fake_codex = tmp_path / "codex.exe"
    fake_codex.write_bytes(b"fixture")
    monkeypatch.setenv("CODEX_PROMPTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(owner, "resolve_provider_command", lambda _provider: [str(fake_codex)])
    monkeypatch.setattr(owner, "require_codex_hook_trust", lambda *_args: 0)
    monkeypatch.setattr(owner, "ledger_helper", lambda: tmp_path / "ledger.py")
    monkeypatch.setattr(owner, "run_ledger", lambda _args: False)

    def forbidden_popen(*_args, **_kwargs):
        raise AssertionError("provider must not start after a ledger launch failure")

    monkeypatch.setattr(owner.subprocess, "Popen", forbidden_popen)
    result = owner.launch(
        "codex",
        ["ledger-denied", "--prompt-file", str(prompt), "--ledger", str(tmp_path / "item")],
    )
    assert result == 1
    verdicts = list((tmp_path / "outputs").glob("*.verdict"))
    assert len(verdicts) == 1
    assert verdicts[0].read_text(encoding="ascii") == "FAILED:nonzero-exit\n"


@pytest.mark.parametrize(("provider_exit", "expected_exit"), ((0, 1), (7, 7)))
def test_terminal_verdict_failure_is_loud_and_preserves_child_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    provider_exit: int,
    expected_exit: int,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fixture\n", encoding="utf-8")
    fake_codex = tmp_path / "codex.exe"
    fake_codex.write_bytes(b"fixture")
    monkeypatch.setenv("CODEX_PROMPTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(owner, "resolve_provider_command", lambda _provider: [str(fake_codex)])
    monkeypatch.setattr(owner, "require_codex_hook_trust", lambda *_args: 0)
    monkeypatch.setattr(owner, "process_start_marker", lambda _pid: None)

    class ProviderProcess:
        pid = 4242
        returncode = provider_exit

        def communicate(self, _body: bytes) -> None:
            return None

    monkeypatch.setattr(owner.subprocess, "Popen", lambda *_args, **_kwargs: ProviderProcess())
    original_write = owner.write_verdict
    writes = 0

    def fail_terminal_write(path: Path, token: str) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("fixture terminal denial")
        original_write(path, token)

    monkeypatch.setattr(owner, "write_verdict", fail_terminal_write)
    result = owner.launch("codex", ["terminal-denied", "--prompt-file", str(prompt)])
    assert result == expected_exit
    assert "could not write terminal verdict" in capsys.readouterr().err
    verdicts = list((tmp_path / "outputs").glob("*.verdict"))
    assert len(verdicts) == 1
    assert verdicts[0].read_text(encoding="ascii") == "LAUNCHED\n"


def test_keyboard_interrupt_leaves_launched_and_cleans_up_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fixture\n", encoding="utf-8")
    fake_codex = tmp_path / "codex.exe"
    fake_codex.write_bytes(b"fixture")
    monkeypatch.setenv("CODEX_PROMPTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(owner, "resolve_provider_command", lambda _provider: [str(fake_codex)])
    monkeypatch.setattr(owner, "require_codex_hook_trust", lambda *_args: 0)
    monkeypatch.setattr(owner, "process_start_marker", lambda _pid: None)
    monkeypatch.setattr(owner, "ledger_helper", lambda: tmp_path / "ledger.py")
    ledger_calls: list[list[str]] = []
    monkeypatch.setattr(owner, "run_ledger", lambda args: ledger_calls.append(args) or True)

    class InterruptedProcess:
        pid = 4242
        returncode = None
        terminated = False
        killed = False

        def communicate(self, _body: bytes) -> None:
            raise KeyboardInterrupt

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

        def wait(self, timeout=None) -> int:
            self.returncode = 130
            return 130

    process = InterruptedProcess()
    monkeypatch.setattr(owner.subprocess, "Popen", lambda *_args, **_kwargs: process)
    result = owner.launch(
        "codex",
        ["interrupted", "--prompt-file", str(prompt), "--ledger", str(tmp_path / "item")],
    )
    assert result == 130
    assert process.terminated
    assert not process.killed
    verdicts = list((tmp_path / "outputs").glob("*.verdict"))
    assert len(verdicts) == 1
    assert verdicts[0].read_text(encoding="ascii") == "LAUNCHED\n"
    assert len(ledger_calls) == 2
    terminal = ledger_calls[1]
    assert terminal[terminal.index("--status") + 1] == "blocked"
    assert terminal[terminal.index("--gate") + 1] == "none"
    assert "nonzero exit (130)" in terminal[terminal.index("--notes") + 1]


@pytest.mark.parametrize("failure_stage", ("pid", "communicate"))
def test_post_popen_oserror_terminates_and_reaps_child(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fixture\n", encoding="utf-8")
    fake_codex = tmp_path / "codex.exe"
    fake_codex.write_bytes(b"fixture")
    monkeypatch.setenv("CODEX_PROMPTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setattr(owner, "resolve_provider_command", lambda _provider: [str(fake_codex)])
    monkeypatch.setattr(owner, "require_codex_hook_trust", lambda *_args: 0)
    monkeypatch.setattr(owner, "process_start_marker", lambda _pid: None)

    class FailingProcess:
        pid = 4242
        returncode = None
        communicated = False
        terminated = False
        killed = False
        wait_calls = 0

        def communicate(self, _body: bytes) -> None:
            self.communicated = True
            if failure_stage == "communicate":
                raise OSError("fixture communicate failure")

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

        def wait(self, timeout=None) -> int:
            self.wait_calls += 1
            if timeout is not None and not self.killed:
                raise subprocess.TimeoutExpired("fixture", timeout)
            self.returncode = 1
            return 1

    process = FailingProcess()
    monkeypatch.setattr(owner.subprocess, "Popen", lambda *_args, **_kwargs: process)
    original_write_private = owner.write_private

    def fail_pid_write(path: Path, data: bytes) -> None:
        if failure_stage == "pid" and path.suffix == ".pid":
            raise OSError("fixture pid-sidecar failure")
        original_write_private(path, data)

    monkeypatch.setattr(owner, "write_private", fail_pid_write)
    result = owner.launch("codex", ["post-popen-oserror", "--prompt-file", str(prompt)])
    assert result == 1
    assert process.communicated is (failure_stage == "communicate")
    assert process.terminated
    assert process.killed
    assert process.wait_calls == 2
    verdicts = list((tmp_path / "outputs").glob("*.verdict"))
    assert len(verdicts) == 1
    assert verdicts[0].read_text(encoding="ascii") == "FAILED:nonzero-exit\n"


def test_trusted_codex_launch_preserves_exact_provider_popen_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("trusted fixture\n", encoding="utf-8")
    codex = tmp_path / "codex.exe"
    codex.write_bytes(b"fixture")
    command = [str(codex), "--transport-owner"]
    codex_home = tmp_path / "codex-home"
    output_root = tmp_path / "outputs"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("CODEX_PROMPTS_DIR", str(output_root))
    monkeypatch.setattr(owner, "resolve_provider_command", lambda _provider: command)
    trust_calls: list[tuple] = []
    monkeypatch.setattr(
        owner,
        "require_codex_hook_trust",
        lambda *args: trust_calls.append(args) or 0,
    )
    monkeypatch.setattr(owner, "process_start_marker", lambda _pid: None)
    captured: dict[str, object] = {}

    class ProviderProcess:
        pid = 4242
        returncode = 0
        def communicate(self, body: bytes) -> None:
            captured["body"] = body

    def fake_popen(arguments, **kwargs):
        captured["arguments"] = arguments
        captured["kwargs"] = kwargs
        return ProviderProcess()

    monkeypatch.setattr(owner.subprocess, "Popen", fake_popen)
    result = owner.launch(
        "codex",
        [
            "exact-argv",
            "--prompt-file", str(prompt),
            "--",
            "--model", "gpt-5.6-sol",
            "-c", "model_reasoning_effort=xhigh",
        ],
    )
    assert result == 0
    arguments = captured["arguments"]
    lastmsg = Path(arguments[arguments.index("--output-last-message") + 1])
    assert arguments == [
        *command,
        "exec",
        "--skip-git-repo-check",
        "--output-last-message",
        str(lastmsg),
        "--model",
        "gpt-5.6-sol",
        "-c",
        "model_reasoning_effort=xhigh",
    ]
    assert trust_calls == [(command, codex_home.resolve(), ROOT.resolve())]
    assert captured["kwargs"]["cwd"] == ROOT.resolve()
    assert captured["kwargs"]["env"]["CODEX_HOME"] == str(codex_home.resolve())
    assert captured["body"] == prompt.read_bytes()
