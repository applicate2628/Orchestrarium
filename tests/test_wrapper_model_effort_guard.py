"""Explicit model-and-effort guards for both Python prompt transports."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from tests.fixtures.codex_hook_fixture import (
    FAKE_CODEX_HOOKS_HOST,
    prepare_codex_home,
)
from tests.fixtures.provider_prompt_projection import (
    materialize_provider_prompt_runtime,
)
from tests.fixtures.runtime_capabilities import requires_windows_process_runner


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/provider_prompt.py"
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


def _projected_entrypoint(tmp_path: Path, provider: str) -> Path:
    scripts = tmp_path / "claude-projection" / "agents" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    materialize_provider_prompt_runtime(ROOT, scripts)
    (scripts / "resolve-agents-mode.py").write_bytes(
        (ROOT / "scripts" / "resolve-agents-mode.py").read_bytes()
    )
    (scripts / "external-prompt-governance.md").write_bytes(
        (ROOT / "shared" / "external-prompt-governance.md").read_bytes()
    )
    (scripts / "external-role-taxonomy.v1.json").write_bytes(
        (ROOT / "shared" / "external-role-taxonomy.v1.json").read_bytes()
    )
    entrypoint = scripts / ENTRYPOINTS[provider].name
    entrypoint.write_bytes(ENTRYPOINTS[provider].read_bytes())
    support = tmp_path / "scripts"
    support.mkdir(exist_ok=True)
    for name in ("check-hook-health.py", "universal_hooks_manifest.py", "agent-run-ledger.py"):
        (support / name).write_bytes((ROOT / "scripts" / name).read_bytes())
    shared = scripts.parent.parent / "shared"
    shared.mkdir(exist_ok=True)
    (scripts.parent / "shared").mkdir(exist_ok=True)
    (scripts.parent / "shared" / "provider-prompt-projections.v1.json").write_bytes(
        (ROOT / "shared" / "provider-prompt-projections.v1.json").read_bytes()
    )
    (scripts.parent / "shared" / "role-routing-policy.v1.json").write_bytes(
        (ROOT / "shared" / "role-routing-policy.v1.json").read_bytes()
    )
    (shared / "AGENTS.shared.md").write_bytes(
        (ROOT / "shared" / "AGENTS.shared.md").read_bytes()
    )
    (shared / "role-routing-policy.v1.json").write_bytes(
        (ROOT / "shared" / "role-routing-policy.v1.json").read_bytes()
    )
    (scripts / "check-hook-health.py").write_bytes(
        (ROOT / "scripts" / "check-hook-health.py").read_bytes()
    )
    return entrypoint


def _make_fake_provider(
    tmp_path: Path, provider: str, *, stdin_capture: Path | None = None
) -> tuple[Path, Path]:
    capture = tmp_path / f"{provider}-argv.json"
    fake = tmp_path / f"fake-{provider}.py"
    fake.write_text(
        "import json,os,pathlib,sys\n"
        "args=sys.argv[1:]\n"
        "if 'app-server' in args:\n"
        f"    import runpy; runpy.run_path({str(FAKE_CODEX_HOOKS_HOST)!r}, run_name='__main__')\n"
        f"pathlib.Path({str(capture)!r}).write_text(json.dumps(args), encoding='utf-8')\n"
        "payload=sys.stdin.buffer.read()\n"
        + (
            f"pathlib.Path({str(stdin_capture)!r}).write_bytes(payload)\n"
            if stdin_capture is not None
            else ""
        )
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
    terminal_receipt = (tmp_path / f"{provider}.receipt").resolve()
    env = os.environ.copy()
    env[BIN_ENV[provider]] = str(fake)
    env[OUTPUT_ENV[provider]] = str(tmp_path / f"{provider}-outputs")
    env["FAKE_ARGV_CAPTURE"] = str(capture)
    if provider == "codex":
        env["CODEX_HOME"] = str(prepare_codex_home(tmp_path))
        env["OPENAI_API_KEY"] = "fake-commercial-credential"
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
            str(_projected_entrypoint(tmp_path, provider)),
            "model-effort-fixture",
            "--prompt-file",
            str(prompt),
            "--terminal-receipt",
            str(terminal_receipt),
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


@pytest.mark.parametrize("provider", ("codex", "claude"))
@requires_windows_process_runner
def test_root_thin_wrapper_delivers_one_governance_frame_then_exact_task_bytes(
    tmp_path: Path, provider: str
) -> None:
    """Catches a root wrapper that bypasses the shared in-memory transport seam."""

    runtime_scripts = tmp_path / "runtime" / "agents" / "scripts"
    runtime_scripts.mkdir(parents=True)
    entrypoint = runtime_scripts / f"invoke-{provider}-prompt.py"
    shutil.copyfile(ROOT / "scripts" / entrypoint.name, entrypoint)
    materialize_provider_prompt_runtime(ROOT, runtime_scripts)
    shutil.copyfile(
        ROOT / "scripts" / "resolve-agents-mode.py",
        runtime_scripts / "resolve-agents-mode.py",
    )
    shutil.copyfile(
        ROOT / "shared" / "external-prompt-governance.md",
        runtime_scripts / "external-prompt-governance.md",
    )
    shutil.copyfile(
        ROOT / "shared" / "external-role-taxonomy.v1.json",
        runtime_scripts / "external-role-taxonomy.v1.json",
    )
    support = tmp_path / "runtime" / "scripts"
    support.mkdir()
    shared = runtime_scripts.parent / "shared"
    shared.mkdir()
    shutil.copyfile(
        ROOT / "shared" / "provider-prompt-projections.v1.json",
        shared / "provider-prompt-projections.v1.json",
    )
    (runtime_scripts.parent / "shared").mkdir(exist_ok=True)
    shutil.copyfile(
        ROOT / "shared" / "role-routing-policy.v1.json",
        runtime_scripts.parent / "shared" / "role-routing-policy.v1.json",
    )
    for name in ("check-hook-health.py", "universal_hooks_manifest.py"):
        shutil.copyfile(ROOT / "scripts" / name, support / name)
        shutil.copyfile(ROOT / "scripts" / name, runtime_scripts / name)
    prompt = tmp_path / "task.md"
    task = b"root-wrapper task\n"
    prompt.write_bytes(task)
    projected_receipt = (tmp_path / "projected.receipt").resolve()
    root_receipt = (tmp_path / "root.receipt").resolve()
    stdin_capture = tmp_path / "provider-stdin.bin"
    fake, _argv = _make_fake_provider(tmp_path, provider, stdin_capture=stdin_capture)
    env = os.environ.copy()
    env[BIN_ENV[provider]] = str(fake)
    env[OUTPUT_ENV[provider]] = str(tmp_path / "outputs")
    if provider == "codex":
        env["CODEX_HOME"] = str(prepare_codex_home(tmp_path))
        env["OPENAI_API_KEY"] = "fake-commercial-credential"
    else:
        env["ANTHROPIC_API_KEY"] = "fake-commercial-credential"

    result = subprocess.run(
        [
            sys.executable,
            str(entrypoint),
            "root-wrapper-fixture",
            "--prompt-file",
            str(prompt),
            "--terminal-receipt",
            str(projected_receipt),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    delivered = stdin_capture.read_bytes()
    capsule = (ROOT / "shared" / "external-prompt-governance.md").read_bytes()
    expected = (
        b"ORCHESTRARIUM_EXTERNAL_GOVERNANCE_V1\n"
        + capsule
        + b"END_ORCHESTRARIUM_EXTERNAL_GOVERNANCE_V1\n\n"
        + task
    )
    assert delivered == expected
    assert delivered.splitlines().count(b"ORCHESTRARIUM_EXTERNAL_GOVERNANCE_V1") == 1
    assert result.stdout.count("ORCHESTRARIUM_PROVIDER_RESULT_V2=") == 1

    root_result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / f"invoke-{provider}-prompt.py"),
            "root-wrapper-fixture",
            "--prompt-file",
            str(prompt),
            "--terminal-receipt",
            str(root_receipt),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert root_result.returncode == 0, root_result.stderr
    assert stdin_capture.read_bytes() == expected


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
    assert frozenset(effort_action.choices) == provider_prompt.EFFORTS | {
        "unsupported"
    }
    assert "unsupported" not in provider_prompt.EFFORTS


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
@requires_windows_process_runner
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
            "--setting-sources",
            "user",
        ]
    )
    assert received[-len(expected) :] == expected


@pytest.mark.parametrize("provider", ("codex", "claude"))
@requires_windows_process_runner
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
            "--allowedTools",
            "Read,Grep",
        ]
    )
    result, capture, _ = _run_transport(tmp_path, provider, ["--", *override])
    assert result.returncode == 0, result.stderr
    received = json.loads(capture.read_text(encoding="utf-8"))
    expected = (
        override
        if provider == "codex"
        else [*override, "--setting-sources", "user"]
    )
    assert received[-len(expected) :] == expected


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
@requires_windows_process_runner
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
    expected_flags = (
        override
        if provider == "codex"
        else [*override, "--setting-sources", "user"]
    )
    assert [event["launchFlags"] for event in selected] == [
        expected_flags,
        expected_flags,
    ]
    assert provider_prompt.parse_provider_result(result.stdout)["launchFlags"] == expected_flags


@requires_windows_process_runner
def test_equal_model_effort_with_different_sandbox_flags_remain_distinguishable(
    tmp_path: Path,
) -> None:
    common = [
        "--model",
        "gpt-5.6-sol",
        "-c",
        "model_reasoning_effort=max",
        "--sandbox",
    ]
    observed: list[tuple[list[str], list[str]]] = []
    for label, sandbox in (("readonly", "read-only"), ("workspace", "workspace-write")):
        case_root = tmp_path / label
        case_root.mkdir()
        result, _, item = _run_transport(
            case_root,
            "codex",
            ["--", *common, sandbox],
            ledger=True,
        )
        assert result.returncode == 0, result.stderr
        assert item is not None
        payload = provider_prompt.parse_provider_result(result.stdout)
        terminal = [
            json.loads(line)
            for line in (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ][-1]
        observed.append((payload["launchFlags"], terminal["launchFlags"]))

    readonly = [*common, "read-only"]
    workspace = [*common, "workspace-write"]
    assert observed == [(readonly, readonly), (workspace, workspace)]
    assert observed[0] != observed[1]


@pytest.mark.parametrize(
    "unsafe_flags",
    (
        ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=max", "--prompt", "secret body"],
        ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=max", "--api-key=secret"],
        ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=max", "-c", "api_key=secret"],
    ),
)
def test_resolved_profile_rejects_prompt_or_secret_bearing_launch_flags(
    unsafe_flags: list[str],
) -> None:
    with pytest.raises(ValueError, match="E_EXTERNAL_LAUNCH_FLAGS_UNSAFE"):
        provider_prompt.resolved_profile("codex", unsafe_flags)


def test_resolved_profile_accepts_documented_nonsecret_claude_io_flags() -> None:
    flags = [
        "-p",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--model",
        "opus",
        "--effort",
        "xhigh",
        "--permission-mode",
        "bypassPermissions",
        "--tools",
        "Read,Grep,Glob",
        "--allowedTools",
        "Read,Grep",
    ]

    resolved, model, effort = provider_prompt.resolved_profile("claude", flags)

    assert resolved == [*flags, "--setting-sources", "user"]
    assert (model, effort) == ("opus", "xhigh")


@pytest.mark.parametrize(
    ("provider", "flags"),
    (
        (
            "claude",
            [
                "-p", "--output-format", "text", "--model", "opus",
                "--effort", "xhigh", "SECRET PROMPT BODY",
            ],
        ),
        (
            "codex",
            [
                "--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=max",
                "-c", 'mcp_servers.demo.env={OPENAI_API_KEY="secret"}',
            ],
        ),
        (
            "codex",
            [
                "--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=max",
                "--add-dir", "C:\\Users\\<you>\\repo",
            ],
        ),
        (
            "claude",
            [
                "-p", "--output-format", "text", "--model", "opus",
                "--effort", "xhigh", "--mcp-config", '{"TOKEN":"secret"}',
            ],
        ),
    ),
)
def test_resolved_profile_rejects_unpersistable_provider_arguments(
    provider: str, flags: list[str]
) -> None:
    with pytest.raises(ValueError, match="E_EXTERNAL_LAUNCH_FLAGS_UNSAFE"):
        provider_prompt.resolved_profile(provider, flags)
