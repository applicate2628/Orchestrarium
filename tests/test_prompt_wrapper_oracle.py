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
        "import pathlib,sys\n"
        "args=sys.argv[1:]\n"
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


def _run_transport(
    tmp_path: Path,
    provider: str,
    *,
    exit_code: int = 0,
    write_lastmsg: bool = True,
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
    if provider == "claude":
        env["ANTHROPIC_API_KEY"] = "fake-commercial-credential"
    result = subprocess.run(
        [
            sys.executable,
            str(ENTRYPOINTS[provider]),
            "oracle-fixture",
            "--prompt-file",
            str(prompt),
            "--ledger",
            str(item),
            "--ledger-role",
            "architecture-reviewer",
            "--ledger-lane",
            "fixture-lane",
            "--ledger-artifact",
            "design.md",
        ],
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
    ("exit_code", "out", "err", "lastmsg", "status", "gate", "note"),
    (
        (1, "GATE: PASS\n", "", "", "blocked", "none", "nonzero exit"),
        (0, "", "", "", "blocked", "none", "empty .out"),
        (0, "GATE: PASS\n", "ERROR: failed\n", "", "blocked", "none", "err markers"),
        (0, "GATE: PASS\n", "", "", "completed", "PASS", "final-line GATE: PASS"),
        (0, "GATE: REVISE\n", "", "", "revise", "REVISE", "final-line GATE: REVISE"),
        (0, "analysis only\n", "", "", "blocked", "none", "not an anchored"),
        (0, "analysis only\n", "", "GATE: PASS\n", "completed", "PASS", "final-line GATE: PASS"),
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
    owner.record_terminal(
        control,
        "codex",
        "gpt-5.6-sol",
        "xhigh",
        "slug",
        "launch-id",
        exit_code,
        out_path,
        err_path,
        lastmsg_path,
    )
    args = captured[0]
    assert args[args.index("--status") + 1] == status
    assert args[args.index("--gate") + 1] == gate
    assert note in args[args.index("--notes") + 1]


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_installed_python_layout_uses_sibling_ledger_helper(
    tmp_path: Path, provider: str
) -> None:
    result, markers = _run_installed_transport(
        tmp_path, provider, ("sibling",)
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
    result, markers = _run_installed_transport(tmp_path, "codex", available)
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
