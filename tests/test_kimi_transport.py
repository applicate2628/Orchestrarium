from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER_PATH = ROOT / "scripts" / "provider_prompt.py"
WRAPPER_PATH = ROOT / "scripts" / "invoke-kimi-prompt.py"


def _load_owner():
    spec = importlib.util.spec_from_file_location("slice_b_kimi_transport", OWNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_kimi_entry_is_thin_and_process_bound() -> None:
    text = WRAPPER_PATH.read_text(encoding="utf-8")
    assert "from provider_prompt import launch" in text
    assert 'launch("kimi", sys.argv[1:])' in text
    assert "subprocess" not in text


def test_kimi_038_plan_is_explicit_k3_prompt_only_and_neutral(tmp_path: Path) -> None:
    owner = _load_owner()
    live_root = tmp_path / "live-repo"
    live_root.mkdir()
    private_root = tmp_path / "private-capture"
    private_root.mkdir()
    task_file = private_root / "prompt.md"
    task_file.write_text("review\n", encoding="utf-8")
    neutral_cwd = private_root / "workspace"

    plan = owner.build_kimi_launch_plan(
        task_file=task_file,
        neutral_cwd=neutral_cwd,
        live_root=live_root,
        provider_flags=[],
    )
    assert plan.argv == (
        "-m",
        "kimi-code/k3",
        "--output-format",
        "stream-json",
        "--agent-file",
        str(task_file.with_name("kimi-agent.md")),
        "--skills-dir",
        str(task_file.parent / "kimi-empty-skills"),
        "-p",
        owner.KIMI_TASK_PROMPT,
    )
    assert plan.cwd == neutral_cwd
    assert not str(live_root) in "\x00".join((*plan.argv, str(plan.cwd)))
    assert plan.stdin == b""
    assert plan.provenance == {
        "runtime_version": "0.38.0",
        "model": "kimi-code/k3",
        "native_effort": "unsupported",
        "independent_verification": "required",
        "mapping_loss": (
            "model-only realization; current Kimi help exposes no "
            "effort/reasoning flag"
        ),
    }


def test_kimi_smoke_rejects_tool_event_before_ordinary_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    task = tmp_path / "prompt.md"
    task.write_text("bounded task\n", encoding="utf-8")
    plan = owner.build_kimi_launch_plan(
        task_file=task,
        neutral_cwd=tmp_path / "neutral",
        live_root=tmp_path / "live",
        provider_flags=[],
    )
    canary = tmp_path / "outside-canary"
    canary.write_text("unchanged", encoding="utf-8")

    class Completed:
        returncode = 0
        stdout = b'{"type":"tool_call","name":"shell"}\n'
        stderr = b""

    monkeypatch.setattr(owner.subprocess, "run", lambda *_args, **_kwargs: Completed())
    with pytest.raises(ValueError, match="^E_KIMI_CONTAINMENT_UNAVAILABLE:"):
        owner.run_kimi_containment_smoke(
            ["fake-kimi"], plan, tmp_path / "live", canary, {"TEMP": "x"}
        )
    assert canary.read_text(encoding="utf-8") == "unchanged"


def test_kimi_smoke_accepts_wrapper_owned_terminal_and_preserves_canary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    task = tmp_path / "prompt.md"
    task.write_text("bounded task\n", encoding="utf-8")
    plan = owner.build_kimi_launch_plan(
        task_file=task,
        neutral_cwd=tmp_path / "neutral",
        live_root=tmp_path / "live",
        provider_flags=[],
    )
    canary = tmp_path / "outside-canary"
    canary.write_text("unchanged", encoding="utf-8")

    class Completed:
        returncode = 0
        stdout = b'{"type":"assistant_message","text":"KIMI_CONTAINMENT_SMOKE_OK"}\n'
        stderr = b""

    monkeypatch.setattr(owner.subprocess, "run", lambda *_args, **_kwargs: Completed())
    owner.run_kimi_containment_smoke(
        ["fake-kimi"], plan, tmp_path / "live", canary, {"TEMP": "x"}
    )
    assert canary.read_text(encoding="utf-8") == "unchanged"


@pytest.mark.parametrize("flag", ("--plan", "-y", "--auto", "-p", "--prompt"))
def test_kimi_rejects_prompt_mode_conflicts_before_spawn(
    tmp_path: Path, flag: str
) -> None:
    owner = _load_owner()
    task_file = tmp_path / "prompt.md"
    task_file.write_text("review\n", encoding="utf-8")
    with pytest.raises(ValueError, match="^E_KIMI_PROMPT_FLAG_CONFLICT:"):
        owner.build_kimi_launch_plan(
            task_file=task_file,
            neutral_cwd=tmp_path / "neutral",
            live_root=tmp_path / "repo",
            provider_flags=[flag],
        )


@pytest.mark.parametrize("flags", (["--effort", "high"], ["--reasoning-effort=high"]))
def test_kimi_rejects_explicit_effort_without_default_or_clamp(
    tmp_path: Path, flags: list[str]
) -> None:
    owner = _load_owner()
    task_file = tmp_path / "prompt.md"
    task_file.write_text("review\n", encoding="utf-8")
    with pytest.raises(ValueError, match="^E_KIMI_EFFORT_UNSUPPORTED:"):
        owner.build_kimi_launch_plan(
            task_file=task_file,
            neutral_cwd=tmp_path / "neutral",
            live_root=tmp_path / "repo",
            provider_flags=flags,
        )


def test_kimi_denied_policy_returns_before_binary_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    owner = _load_owner()
    prompt = tmp_path / "prompt.md"
    prompt.write_text("implement\n", encoding="utf-8")
    probed = False

    def forbidden_probe(_provider: str):
        nonlocal probed
        probed = True
        raise AssertionError("binary probe must be unreachable")

    monkeypatch.setattr(owner, "resolve_provider_command", forbidden_probe)
    result = owner.launch(
        "kimi",
        [
            "denied",
            "--prompt-file",
            str(prompt),
            "--task-class",
            "engineering",
            "--role",
            "worker",
        ],
    )
    assert result == 1
    assert not probed
    assert "E_KIMI_DISPATCH_DENIED" in capsys.readouterr().err


def test_kimi_quota_unavailable_returns_before_prompt_capture_or_binary_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    owner = _load_owner()
    prompt = tmp_path / "prompt.md"
    prompt.write_text("review\n", encoding="utf-8")
    monkeypatch.setattr(
        owner,
        "resolve_external_policy",
        lambda *_args: {
            "status": "external-required",
            "requiredEffort": "high",
            "nativeEffort": "unsupported",
            "effortMappingLoss": "no-native-effort-control",
            "mutationClass": "read-only",
            "independentVerification": True,
            "finalAuthorizingRole": False,
        },
    )
    monkeypatch.setattr(owner, "require_transport_projection_parity", lambda: None)
    monkeypatch.setattr(
        owner, "prompt_bytes", lambda _control: (_ for _ in ()).throw(AssertionError("no prompt read"))
    )
    monkeypatch.setattr(
        owner, "resolve_kimi_executable", lambda *_args: (_ for _ in ()).throw(AssertionError("no probe"))
    )
    assert owner.launch(
        "kimi",
        ["review", "--prompt-file", str(prompt), "--task-class", "review", "--role", "qa-engineer"],
    ) != 0
    assert "E_KIMI_READINESS_UNVERIFIED" in capsys.readouterr().err


def test_kimi_exact_executable_rejects_ambient_override_and_script(tmp_path: Path) -> None:
    owner = _load_owner()
    home = tmp_path / "home"
    exact = home / ".kimi-code" / "bin" / "kimi.exe"
    exact.parent.mkdir(parents=True)
    exact.write_bytes(b"fixture")
    assert owner.resolve_kimi_executable(home, {}) == exact
    with pytest.raises(ValueError, match="^E_KIMI_IDENTITY_INVALID:"):
        owner.resolve_kimi_executable(home, {"KIMI_BIN": str(exact)})


def test_kimi_requires_the_exact_accepted_effort_loss_policy() -> None:
    owner = _load_owner()
    accepted = {
        "status": "external-required",
        "requiredEffort": "high",
        "nativeEffort": "unsupported",
        "effortMappingLoss": "no-native-effort-control",
        "mutationClass": "read-only",
        "independentVerification": True,
        "finalAuthorizingRole": False,
    }
    assert owner.require_external_realization("kimi", accepted) == accepted
    rejected = dict(accepted)
    rejected["effortMappingLoss"] = "runtime-default-only"
    with pytest.raises(ValueError, match="^E_KIMI_EFFORT_UNSUPPORTED:"):
        owner.require_external_realization("kimi", rejected)
    rejected_final = dict(accepted)
    rejected_final["finalAuthorizingRole"] = True
    with pytest.raises(ValueError, match="^E_KIMI_EFFORT_UNSUPPORTED:"):
        owner.require_external_realization("kimi", rejected_final)


def test_external_result_envelope_is_explicitly_nonauthorizing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _load_owner()
    outcome = owner.FinalOutcome(
        0, "COMPLETE:EXTERNAL_NONAUTHORIZING", "completed", "PASS", "advisory",
        0, "COMPLETE:EXTERNAL_NONAUTHORIZING", "completed", "PASS", "advisory",
        "complete", 0, "", False, 0,
    )
    stream = io.StringIO()
    monkeypatch.setattr(owner.sys, "stdout", stream)
    owner.emit_provider_result(
        "kimi", "kimi-code/k3", "unsupported", "GATE: PASS", outcome,
        cancelled=False, timed_out=False,
    )
    payload = owner.parse_provider_result(stream.getvalue())
    assert payload["authorizing"] is False
    assert payload["closesRunIds"] == []
    assert payload["terminalClass"] == "external-nonauthorizing"
    assert payload["actualExecutionPath"] == "direct-external-cli"
    assert payload["token"] == "COMPLETE:EXTERNAL_NONAUTHORIZING"


def test_kimi_child_environment_and_agent_file_are_tool_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    monkeypatch.setenv("PATH", "forbidden")
    monkeypatch.setenv("API_KEY", "forbidden")
    environment = owner.external_child_environment("kimi")
    assert "PATH" not in environment and "API_KEY" not in environment
    assert environment["KIMI_CODE_EXPERIMENTAL_FLAG"] == "1"
    monkeypatch.setenv("KIMI_PROMPTS_DIR", str((tmp_path / "captures").resolve()))
    lifecycle = owner.RunCaptureLifecycle.create("kimi", "fixture")
    lifecycle.initialize(b"bounded snapshot")
    lifecycle.initialize_kimi_agent(b"bounded snapshot")
    agent = lifecycle.kimi_agent_path.read_text(encoding="utf-8")
    assert "tools: []" in agent and "subagents: []" in agent
    assert (lifecycle.run_dir / "kimi-empty-skills").is_dir()
    assert lifecycle.cleanup().clean


def test_external_cleanup_failure_is_unverified_not_failed() -> None:
    owner = _load_owner()
    terminal = owner.TerminalResult(
        Path("evidence"), "completed", "PASS", "advisory",
        "COMPLETE:EXTERNAL_NONAUTHORIZING", 0,
    )
    outcome = owner.combine_terminal_outcomes(
        0, terminal, owner.CleanupResult(("API_KEY=secret",), True),
        None, external=True,
    )
    assert outcome.token == "UNVERIFIED:E_EXTERNAL_CAPTURE_CLEANUP"
    assert outcome.status == "blocked" and outcome.gate == "none"
    assert "secret" not in outcome.cleanup_diagnostic
