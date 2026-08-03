"""Explicit model-and-effort guards for both Python prompt transports."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from tests.fixtures.codex_hook_fixture import (
    FAKE_CODEX_HOOKS_HOST,
    prepare_codex_home,
)


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src.claude/agents/scripts/provider_prompt.py"
ENTRYPOINTS = {
    "codex": ROOT / "src.claude/agents/scripts/invoke-codex-prompt.py",
    "claude": ROOT / "src.claude/agents/scripts/invoke-claude-prompt.py",
}
BIN_ENV = {"codex": "CODEX_BIN", "claude": "CLAUDE_BIN"}
OUTPUT_ENV = {"codex": "CODEX_PROMPTS_DIR", "claude": "CLAUDE_PROMPTS_DIR"}
LEDGER_MODULE = ROOT / "scripts/agent-run-ledger.py"
spec = importlib.util.spec_from_file_location("provider_prompt_effort_test", MODULE)
assert spec and spec.loader
provider_prompt = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = provider_prompt
spec.loader.exec_module(provider_prompt)


def _make_fake_provider(tmp_path: Path, provider: str) -> tuple[Path, Path]:
    capture = tmp_path / f"{provider}-argv.json"
    fake = tmp_path / f"fake-{provider}.py"
    fake.write_text(
        "import json,os,pathlib,sys\n"
        "args=sys.argv[1:]\n"
        "if 'app-server' in args:\n"
        f"    import runpy; runpy.run_path({str(FAKE_CODEX_HOOKS_HOST)!r}, run_name='__main__')\n"
        "pathlib.Path(os.environ['FAKE_ARGV_CAPTURE']).write_text("
        "json.dumps(args), encoding='utf-8')\n"
        "sys.stdin.buffer.read()\n"
        + (
            "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'GATE: PASS\\n'}}))\n"
            if provider == "codex"
            else "print('GATE: PASS')\n"
        ),
        encoding="utf-8",
    )
    return fake, capture


def _make_work_item(tmp_path: Path, provider: str) -> Path:
    item = (
        tmp_path
        / "work-items"
        / "active"
        / f"2026-01-01-model-effort-{provider}"
    )
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


def _run_transport(
    tmp_path: Path,
    provider: str,
    extra: list[str],
    *,
    ledger: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path, Path | None]:
    fake, capture = _make_fake_provider(tmp_path, provider)
    prompt = tmp_path / f"{provider}.md"
    prompt.write_text("fixture prompt\n", encoding="utf-8")
    env = os.environ.copy()
    env[BIN_ENV[provider]] = str(fake)
    env[OUTPUT_ENV[provider]] = str(tmp_path / f"{provider}-outputs")
    env["FAKE_ARGV_CAPTURE"] = str(capture)
    if provider == "codex":
        env["CODEX_HOME"] = str(prepare_codex_home(tmp_path))
    else:
        env["ANTHROPIC_API_KEY"] = "fake-commercial-credential"
    item = _make_work_item(tmp_path, provider) if ledger else None
    ledger_args = (
        [
            "--ledger",
            str(item),
            "--ledger-role",
            "architecture-reviewer",
            "--ledger-lane",
            "model-effort-fixture",
            "--ledger-artifact",
            "design.md",
        ]
        if item is not None
        else []
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ENTRYPOINTS[provider]),
            "model-effort-fixture",
            "--prompt-file",
            str(prompt),
            *ledger_args,
            *extra,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    return result, capture, item


@pytest.mark.parametrize(
    ("provider", "flags", "model", "effort"),
    (
        ("codex", [], "gpt-5.6-sol", "xhigh"),
        ("claude", [], "opus", "xhigh"),
        (
            "codex",
            ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=max"],
            "gpt-5.6-sol",
            "max",
        ),
        (
            "claude",
            ["-p", "--output-format", "text", "--model", "sonnet", "--effort", "high"],
            "sonnet",
            "high",
        ),
    ),
)
def test_full_profile_resolves(
    provider: str, flags: list[str], model: str, effort: str
) -> None:
    resolved, actual_model, actual_effort = provider_prompt.resolved_profile(provider, flags)
    assert resolved
    assert (actual_model, actual_effort) == (model, effort)


@pytest.mark.parametrize(
    ("provider", "flags"),
    (
        ("codex", ["-c", "model_reasoning_effort=max"]),
        ("codex", ["--model", "gpt-5.6-sol"]),
        ("claude", ["--effort", "xhigh"]),
        ("claude", ["--model", "opus"]),
    ),
)
def test_partial_override_fails_closed(provider: str, flags: list[str]) -> None:
    with pytest.raises(ValueError, match="A12 violation"):
        provider_prompt.resolved_profile(provider, flags)


def test_effort_enum_is_shared_with_ledger_contract() -> None:
    ledger_spec = importlib.util.spec_from_file_location(
        "agent_run_ledger_effort_test", LEDGER_MODULE
    )
    assert ledger_spec and ledger_spec.loader
    ledger = importlib.util.module_from_spec(ledger_spec)
    ledger_spec.loader.exec_module(ledger)
    parser = ledger.build_parser()
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    append_parser = subparsers.choices["append"]
    effort_action = next(
        action for action in append_parser._actions if action.dest == "effort"
    )
    assert provider_prompt.EFFORTS == frozenset(effort_action.choices)


def test_control_flags_before_topic_are_not_forwarded() -> None:
    parsed = provider_prompt.parse_control(
        ["--prompt-file", "prompt.md", "--ledger", "item", "topic", "--model", "opus", "--effort", "max"]
    )
    assert parsed.topic == "topic"
    assert parsed.prompt_file == Path("prompt.md")
    assert parsed.ledger == "item"
    assert parsed.provider_flags == ["--model", "opus", "--effort", "max"]


def test_control_flags_after_topic_are_not_forwarded() -> None:
    parsed = provider_prompt.parse_control(
        ["topic", "--model", "opus", "--prompt-file", "prompt.md", "--effort", "max"]
    )
    assert parsed.topic == "topic"
    assert parsed.prompt_file == Path("prompt.md")
    assert parsed.provider_flags == ["--model", "opus", "--effort", "max"]


def test_explicit_boundary_forwards_control_like_provider_flags() -> None:
    parsed = provider_prompt.parse_control(
        ["topic", "--", "--prompt-file", "provider.md", "--model", "opus", "--effort", "max"]
    )
    assert parsed.topic == "topic"
    assert parsed.prompt_file is None
    assert parsed.provider_flags == [
        "--prompt-file",
        "provider.md",
        "--model",
        "opus",
        "--effort",
        "max",
    ]


def test_conflicting_singular_control_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="conflicting values"):
        provider_prompt.parse_control(
            ["--prompt-file", "first.md", "topic", "--prompt-file", "second.md"]
        )


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_default_profile_reaches_fake_provider_with_explicit_model_and_effort(
    tmp_path: Path, provider: str
) -> None:
    result, capture, _ = _run_transport(tmp_path, provider, [])
    assert result.returncode == 0, result.stderr
    received = json.loads(capture.read_text(encoding="utf-8"))
    expected = (
        ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=xhigh"]
        if provider == "codex"
        else [
            "-p",
            "--output-format",
            "text",
            "--model",
            "opus",
            "--effort",
            "xhigh",
        ]
    )
    assert received[-len(expected) :] == expected


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_full_profile_override_reaches_fake_provider_byte_for_byte(
    tmp_path: Path, provider: str
) -> None:
    override = (
        ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=max"]
        if provider == "codex"
        else [
            "-p",
            "--output-format",
            "text",
            "--model",
            "sonnet",
            "--effort",
            "high",
        ]
    )
    result, capture, _ = _run_transport(tmp_path, provider, ["--", *override])
    assert result.returncode == 0, result.stderr
    received = json.loads(capture.read_text(encoding="utf-8"))
    assert received[-len(override) :] == override


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_partial_override_fails_before_fake_provider_launch(
    tmp_path: Path, provider: str
) -> None:
    partial = (
        ["-c", "model_reasoning_effort=max"]
        if provider == "codex"
        else ["--effort", "high"]
    )
    result, capture, _ = _run_transport(tmp_path, provider, ["--", *partial])
    assert result.returncode != 0
    assert "A12 violation" in result.stderr
    assert not capture.exists()
    assert result.stdout == ""


@pytest.mark.parametrize("provider", ("codex", "claude"))
def test_launch_and_terminal_ledger_events_record_resolved_profile(
    tmp_path: Path, provider: str
) -> None:
    override = (
        ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=max"]
        if provider == "codex"
        else [
            "-p",
            "--output-format",
            "text",
            "--model",
            "sonnet",
            "--effort",
            "high",
        ]
    )
    result, _, item = _run_transport(
        tmp_path, provider, ["--", *override], ledger=True
    )
    assert result.returncode == 0, result.stderr
    assert item is not None
    events = [
        json.loads(line)
        for line in (item / "agent-runs.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]
    selected = [
        event
        for event in events
        if event.get("eventKind") in {"launch", "terminal"}
    ]
    assert [event["eventKind"] for event in selected] == ["launch", "terminal"]
    expected = (
        ("gpt-5.6-sol", "max")
        if provider == "codex"
        else ("sonnet", "high")
    )
    assert [(event["model"], event["effort"]) for event in selected] == [
        expected,
        expected,
    ]
