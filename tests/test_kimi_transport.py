from __future__ import annotations

import gc
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tomllib
import tracemalloc
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER_PATH = ROOT / "scripts" / "provider_prompt.py"
WRAPPER_PATH = ROOT / "scripts" / "invoke-kimi-prompt.py"
INSTALLER_PATH = ROOT / "scripts" / "production_installer.py"
CODEX_UI_PROMPT_PATHS = (
    ROOT / "src.codex/skills/consultant/agents/openai.yaml",
    ROOT / "src.codex/skills/init-project/agents/openai.yaml",
    ROOT / "src.codex/skills/second-opinion/agents/openai.yaml",
)
EXPECTED_KIMI_TERMINAL_INSTRUCTION = (
    b"Your final nonblank line must be exactly one of: GATE: PASS, "
    b"GATE: REVISE, GATE: BLOCKED. Do not emit any other gate-like line.\n"
)
_SYNTHETIC_AUTH_SCHEME = "Bear" + "er"
_SYNTHETIC_AUTH_PAYLOAD = "bearer-" + "payload"
_SYNTHETIC_AUTH_VALUE = f"{_SYNTHETIC_AUTH_SCHEME} {_SYNTHETIC_AUTH_PAYLOAD}"


def _load_owner():
    spec = importlib.util.spec_from_file_location("kimi_unavailable_owner", OWNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_installer():
    spec = importlib.util.spec_from_file_location("kimi_installer_owner", INSTALLER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_kimi_wrapper_stays_thin() -> None:
    text = WRAPPER_PATH.read_text(encoding="utf-8")
    assert "from provider_prompt import kimi_main" in text
    assert "kimi_main(sys.argv[1:])" in text
    assert "subprocess" not in text


def test_codex_ui_prompts_describe_fixed_no_enrollment_kimi_launch() -> None:
    for path in CODEX_UI_PROMPT_PATHS:
        prompt = path.read_text(encoding="utf-8")
        assert "Windows-enrolled" not in prompt
        assert "omitted Kimi capability file keeps tools/MCP/subagents empty with permission reject" in prompt
        assert "validated capability file" in prompt
        assert "ordinary launch does not consult enrollment" in prompt.lower()


def test_installer_kimi_enrollment_actions_are_explicit_and_mutually_exclusive() -> None:
    installer = _load_installer()

    replacement = installer._parser("codex").parse_args(
        ["--global", "--replace-kimi-enrollment"]
    )
    assert replacement.replace_kimi_enrollment is True
    assert replacement.enroll_kimi is False
    with pytest.raises(SystemExit):
        installer._parser("codex").parse_args(
            ["--global", "--enroll-kimi", "--replace-kimi-enrollment"]
        )


def test_installer_kimi_offline_policy_is_explicit_and_bounded() -> None:
    installer = _load_installer()
    parser = installer._parser("codex")

    parsed = parser.parse_args(
        ["--global", "--enroll-kimi", "--kimi-offline-policy", "24h"]
    )
    assert parsed.kimi_offline_policy == "24h"
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["--global", "--enroll-kimi", "--kimi-offline-policy", "30d"]
        )


def test_orphan_kimi_offline_policy_fails_before_target_or_transaction(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    installer = _load_installer()
    monkeypatch.setattr(
        installer,
        "_target",
        lambda *_args: pytest.fail("orphan option reached target resolution"),
    )

    assert installer.install(
        "codex", ["--global", "--kimi-offline-policy", "24h"]
    ) == 1
    assert "E_KIMI_OFFLINE_POLICY_ORPHAN" in capsys.readouterr().err


def test_kimi_launch_uses_fixed_executable_without_admission_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    home = (tmp_path / "user").resolve()
    executable = home / ".kimi-code" / "bin" / "kimi.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"synthetic-kimi")
    monkeypatch.setenv("USERPROFILE", str(home))

    command, binding = owner._resolve_enrolled_kimi_launch()

    assert command == [str(executable.resolve())]
    assert binding is None
    assert not (home / ".codex" / "orchestrarium-runtime" / "kimi").exists()


def test_kimi_missing_fixed_executable_has_actionable_unavailable_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    home = (tmp_path / "user").resolve()
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))

    with pytest.raises(ValueError, match="^E_KIMI_EXECUTABLE_UNAVAILABLE:"):
        owner._resolve_enrolled_kimi_launch()

    assert not (home / ".codex" / "orchestrarium-runtime" / "kimi").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction contract")
def test_kimi_launch_follows_fixed_path_junction_without_enrollment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    home = (tmp_path / "user").resolve()
    home.mkdir()
    physical = (tmp_path / "physical-kimi-home").resolve()
    executable = physical / "bin" / "kimi.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"synthetic-kimi")
    junction = home / ".kimi-code"
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(physical)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        pytest.skip(f"junction unavailable: {result.stderr.strip()}")
    monkeypatch.setenv("USERPROFILE", str(home))

    command, binding = owner._resolve_enrolled_kimi_launch()

    assert command == [str(executable)]
    assert binding is None
    assert not (home / ".codex" / "orchestrarium-runtime" / "kimi").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows file-symlink contract")
def test_kimi_launch_keeps_profile_after_fixed_file_symlink_resolves_to_renamed_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    home = (tmp_path / "user").resolve()
    link = home / ".kimi-code" / "bin" / "kimi.exe"
    link.parent.mkdir(parents=True)
    target = (tmp_path / "physical" / "current-kimi-client.exe").resolve()
    target.parent.mkdir()
    target.write_bytes(b"synthetic-kimi")
    try:
        link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"file symlink unavailable: {exc}")
    monkeypatch.setenv("USERPROFILE", str(home))

    command, binding = owner._resolve_enrolled_kimi_launch()

    assert command == [str(target)]
    assert binding is None
    assert owner.provider_windows_argv_profile_id("kimi", target) == (
        owner.KIMI_WINDOWS_PROFILE_V1.profile_id
    )


def test_kimi_readiness_diagnostic_checks_version_and_required_help_flags(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    home = (tmp_path / "user").resolve()
    executable = home / ".kimi-code" / "bin" / "kimi.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"synthetic-kimi")
    calls: list[tuple[str, ...]] = []

    def probe(resolution, argv: tuple[str, ...]) -> bytes:
        assert resolution.command == (str(executable.resolve()),)
        calls.append(argv)
        if argv == ("--version",):
            return b"0.42.0\n"
        return b"Commands: acp\n"

    command = owner._diagnose_kimi_readiness(home, probe_runner=probe)

    assert command == [str(executable.resolve())]
    assert calls == [("--version",), ("--help",)]


def test_kimi_capability_diagnostic_exposes_bounded_help_and_exact_support(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    home = (tmp_path / "user").resolve()
    executable = home / ".kimi-code" / "bin" / "kimi.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"synthetic-kimi")
    calls: list[tuple[str, ...]] = []
    help_text = (
        "Commands: acp\n"
        "--agent-file <path> --skills-dir <dir> --model <model>\n"
        "--output-format <format> supports text and stream-json\n"
        "--prompt <prompt>\n"
        "--mcp-config-file <path> repeatable; default: none\n"
        "--mcp-config <json> repeatable; default: none\n"
    )

    def probe(resolution, argv: tuple[str, ...]) -> bytes:
        assert resolution.command == (str(executable.resolve()),)
        calls.append(argv)
        return b"0.42.0\n" if argv == ("--version",) else help_text.encode("utf-8")

    report = owner._diagnose_kimi_readiness(
        home, probe_runner=probe, include_capabilities=True
    )

    assert report["schemaVersion"] == 1
    assert report["kind"] == "kimi-capability-readiness"
    assert report["version"] == "0.42.0"
    assert report["command"] == [str(executable.resolve())]
    assert report["launchEnvironment"] == {
        "KIMI_CODE_EXPERIMENTAL_FLAG": "1",
        "KIMI_CODE_NO_AUTO_UPDATE": "1",
        "DO_NOT_TRACK": "1",
        "isolatedKimiCodeHome": True,
    }
    assert report["help"] == {
        "bytes": len(help_text.encode("utf-8")),
        "sha256": hashlib.sha256(help_text.encode("utf-8")).hexdigest(),
        "text": help_text,
    }
    assert report["support"]["structuredOutput"] == {
        "outputFormatFlag": True,
        "streamJsonValue": True,
        "supported": True,
    }
    assert report["support"]["selectedMcpConfiguration"] == {
        "flags": ["--mcp-config-file", "--mcp-config"],
        "repeatable": True,
        "noDefaultConfig": True,
        "supported": True,
    }
    assert report["support"]["independentChildControls"] == {
        "agentFileFlag": True,
        "toolsField": False,
        "subagentsField": False,
        "defaultToolsDisabled": True,
        "defaultChildrenDisabled": True,
        "runtimeVerified": False,
    }
    assert calls == [("--version",), ("--help",)]


def test_kimi_capability_diagnostic_reports_absent_installed_help_features(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    home = (tmp_path / "user").resolve()
    executable = home / ".kimi-code" / "bin" / "kimi.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"synthetic-kimi")
    base_help = "Commands: acp\n--agent-file --skills-dir --model --output-format --prompt\n"

    report = owner._diagnose_kimi_readiness(
        home,
        probe_runner=lambda _resolution, argv: (
            b"0.42.0\n" if argv == ("--version",) else base_help.encode("utf-8")
        ),
        include_capabilities=True,
    )

    assert report["support"]["structuredOutput"]["supported"] is False
    assert report["support"]["selectedMcpConfiguration"] == {
        "flags": [],
        "repeatable": False,
        "noDefaultConfig": False,
        "supported": False,
    }
    assert report["help"]["text"] == base_help


@pytest.mark.parametrize("argv", (("--version",), ("--help",)))
def test_kimi_readiness_diagnostic_uses_actual_sealed_launch_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: tuple[str, ...]
) -> None:
    owner = _load_owner()
    executable = (tmp_path / "kimi.exe").resolve()
    executable.write_bytes(b"synthetic-kimi")
    resolution = owner.ResolvedProviderCommand(
        (str(executable),), executable, "explicit-absolute-binding"
    )
    observed: list[object] = []

    class Sink:
        def bytes_for(self, stream: str) -> bytes:
            return b"installed help\n" if stream == "stdout" else b""

    class Runner:
        def mint_memory_capture_sink(self) -> Sink:
            return Sink()

        def run(self, request):
            observed.append(request)
            return SimpleNamespace(
                outcome="success",
                target_exit_code=0,
                resources_closed=True,
                tree=SimpleNamespace(tree_empty=True),
            )

        def close(self) -> None:
            return None

    def auth(provider: str):
        assert provider == "kimi"
        return SimpleNamespace(
            child_environment={
                "PATH": "synthetic-path",
                "SYSTEMROOT": "C:\\Windows",
                "KIMI_CODE_EXPERIMENTAL_FLAG": "1",
                "KIMI_CODE_NO_AUTO_UPDATE": "1",
                "DO_NOT_TRACK": "1",
            }
        )

    monkeypatch.setattr(owner, "ProcessRunnerV1", Runner)
    monkeypatch.setattr(owner, "resolve_provider_auth_configuration", auth)

    assert owner._default_kimi_readiness_probe(resolution, argv) == b"installed help\n"
    request = observed[0]
    environment = {row.name: row.value for row in request.environment}
    assert environment["PATH"] == "synthetic-path"
    assert environment["SYSTEMROOT"] == "C:\\Windows"
    assert environment["KIMI_CODE_EXPERIMENTAL_FLAG"] == "1"
    assert environment["KIMI_CODE_NO_AUTO_UPDATE"] == "1"
    assert environment["DO_NOT_TRACK"] == "1"
    assert Path(environment["KIMI_CODE_HOME"]).resolve() == Path(request.cwd).resolve()
    assert request.argv == (str(executable), *argv)
    assert request.windows_argv_profile_id == owner.KIMI_WINDOWS_PROFILE_V1.probe_profile_id


def test_kimi_capability_command_is_json_only_and_never_launches_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()
    home = (tmp_path / "user").resolve()
    report = {"schemaVersion": 1, "kind": "kimi-capability-readiness"}

    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(
        owner,
        "_diagnose_kimi_readiness",
        lambda selected_home, *, include_capabilities=False: (
            report
            if selected_home == home and include_capabilities
            else pytest.fail("capability command used the wrong diagnostic contract")
        ),
    )
    monkeypatch.setattr(
        owner,
        "launch",
        lambda *_args, **_kwargs: pytest.fail("capability diagnostic reached provider launch"),
    )

    assert owner.kimi_main(["--diagnose-capabilities"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == report


def test_kimi_maintenance_aliases_share_one_nonwriting_readiness_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    owner = _load_owner()
    home = (tmp_path / "user").resolve()
    runtime = (tmp_path / "runtime-must-stay-absent").resolve()
    observed: list[Path] = []

    def diagnose(selected_home: Path) -> list[str]:
        observed.append(selected_home)
        return [str(selected_home / ".kimi-code" / "bin" / "kimi.exe")]

    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(owner, "_diagnose_kimi_readiness", diagnose, raising=False)
    monkeypatch.setattr(
        owner,
        "launch",
        lambda *_args, **_kwargs: pytest.fail("maintenance reached provider launch"),
    )

    assert owner.kimi_main(["--enroll-executable"]) == 0
    assert owner.kimi_main(["--replace-kimi-enrollment"]) == 0
    assert owner.kimi_main(["--verify-enrollment"]) == 0
    assert observed == [home, home, home]
    assert not runtime.exists()
    assert not (home / ".codex" / "orchestrarium-runtime" / "kimi").exists()
    output = capsys.readouterr().out
    assert output.count("KIMI-EXECUTABLE-READINESS: PASS") == 3
    assert "ENROLLMENT" not in output
    assert "REPLACEMENT" not in output

    with pytest.raises(ValueError, match="^E_KIMI_OFFLINE_POLICY_OBSOLETE$"):
        owner.enroll_kimi_executable(
            home,
            runtime,
            dry_run=False,
            offline_policy="24h",
        )
    assert observed == [home, home, home]
    assert not runtime.exists()


def test_kimi_help_is_local_and_never_enters_policy_or_provider_launch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    owner = _load_owner()
    monkeypatch.setattr(
        owner,
        "launch",
        lambda *_args, **_kwargs: pytest.fail("help reached provider launch"),
    )

    assert owner.kimi_main(["--help"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert "usage: invoke-kimi-prompt.py" in captured.out
    assert "--prompt-file" in captured.out
    assert "kimi-code/k3" in captured.out


def test_provider_owner_accepts_current_35_role_taxonomy() -> None:
    owner = _load_owner()

    roles, reviewers, workers, unsupported = owner._external_role_taxonomy()

    assert len(roles) == 35
    assert "scientific-software-engineer" in roles
    assert reviewers | workers | unsupported | {"consultant"} == roles


@pytest.mark.parametrize(
    "document",
    (
        {"schemaVersion": 2, "roles": {"consultant": "consultant"}},
        {
            "schemaVersion": 1,
            "roles": {"consultant": "consultant", "analyst": "invalid-lane"},
        },
    ),
)
def test_provider_owner_still_rejects_invalid_taxonomy_schema_or_lane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    document: dict[str, object],
) -> None:
    owner = _load_owner()
    source_root = tmp_path / "fixture"
    script = source_root / "scripts" / "provider_prompt.py"
    taxonomy = source_root / "shared" / owner.EXTERNAL_ROLE_TAXONOMY_NAME
    script.parent.mkdir(parents=True)
    taxonomy.parent.mkdir(parents=True)
    script.write_text("fixture\n", encoding="utf-8")
    payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
    taxonomy.write_bytes(payload)
    monkeypatch.setattr(owner, "__file__", str(script))
    monkeypatch.setattr(owner, "EXTERNAL_ROLE_TAXONOMY_SHA256", hashlib.sha256(payload).hexdigest())

    with pytest.raises(ValueError, match="^E_EXTERNAL_PROVENANCE_ROLE_INVALID"):
        owner._external_role_taxonomy()


@pytest.mark.parametrize(
    "argv",
    (
        ["--enroll-executable", "topic"],
        ["--verify-enrollment", "--enroll-executable"],
        ["--replace-kimi-enrollment", "--enroll-executable"],
        ["--replace-kimi-enrollment", "topic"],
        ["topic", "--verify-enrollment"],
        ["--diagnose-capabilities", "topic"],
    ),
)
def test_kimi_maintenance_flags_fail_closed_when_combined(
    argv: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    owner = _load_owner()
    monkeypatch.setattr(
        owner,
        "launch",
        lambda _provider, _argv: (_ for _ in ()).throw(
            AssertionError("invalid maintenance arguments reached provider launch")
        ),
    )

    assert owner.kimi_main(argv) == 1
    assert "E_KIMI_MAINTENANCE_ARGUMENTS_INVALID" in capsys.readouterr().err


def test_kimi_profile_resolves_only_high_or_max_effort_without_provider_flags() -> None:
    owner = _load_owner()
    assert owner.resolved_profile("kimi", []) == ([], "kimi-code/k3", "high")
    assert owner.resolved_profile("kimi", [], kimi_effort="max") == (
        [],
        "kimi-code/k3",
        "max",
    )
    assert owner.parse_control(["fixture"], provider="kimi").kimi_effort == "high"
    assert owner.parse_control(
        ["fixture", "--kimi-effort", "max"], provider="kimi"
    ).kimi_effort == "max"
    with pytest.raises(ValueError, match="E_KIMI_EFFORT_INVALID"):
        owner.parse_control(["fixture", "--kimi-effort", "low"], provider="kimi")
    with pytest.raises(ValueError, match="E_KIMI_PROFILE_FIXED"):
        owner.resolved_profile("kimi", ["--model", "other"])


def test_kimi_wrapper_entry_freezes_policy_bound_max_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    captured: list[object] = []
    # Exercise policy composition on every host; receipt I/O is a separate suite.
    monkeypatch.setattr(owner, "os", SimpleNamespace(**{**vars(os), "name": "nt"}))
    monkeypatch.setattr(owner.TerminalReceiptV1, "reserve", classmethod(
        lambda _cls, _path: SimpleNamespace(committed=False, close=lambda: None)
    ))

    def stop_before_provider(
        _provider, _argv, _runner, *, prevalidated, reserved_run, **_kwargs
    ) -> int:
        captured.append((prevalidated, reserved_run))
        return 0

    monkeypatch.setattr(owner, "_launch_with_runner", stop_before_provider)
    receipt = tmp_path / "kimi-effort.receipt"

    assert owner.launch(
        "kimi",
        [
            "fixture",
            "--terminal-receipt",
            str(receipt),
            "--task-class",
            "review",
            "--role",
            "qa-engineer",
            "--kimi-effort",
            "max",
        ],
    ) == 0

    prevalidated, _reserved_run = captured[0]
    assert prevalidated.effort == "max"
    assert prevalidated.flags == ()
    assert prevalidated.provenance is not None
    assert prevalidated.provenance.effort == "max"
    assert prevalidated.provenance.launch_flags == ()
    assert owner.require_exact_execution_provenance(
        prevalidated.provenance, prevalidated.provenance
    ) == prevalidated.provenance


def test_kimi_acp_argv_is_exact() -> None:
    owner = _load_owner()
    assert owner.kimi_provider_args() == ["acp"]


def test_kimi_acp_request_has_programmatic_dialogue_and_no_static_stdin(tmp_path: Path) -> None:
    owner = _load_owner()
    executable = tmp_path / "kimi.exe"
    executable.write_bytes(b"synthetic-kimi")
    observed: list[tuple[object, object]] = []

    class Sink:
        def bytes_for(self, _stream: str) -> bytes:
            return b""

    class Runner:
        def mint_memory_capture_sink(self) -> Sink:
            return Sink()

        def run(self, request, *, dialogue=None):
            observed.append((request, dialogue))
            return object()

    provider_args = owner.kimi_provider_args()
    exchange = owner.KimiAcpOneShotV1(b"fixture", str(tmp_path))
    dialogue = owner.ProcessDialogueV1(
        owner.KIMI_WINDOWS_PROFILE_V1.profile_id, exchange
    )
    expected_binding = owner.ExecutableBindingV1(
        str(executable.resolve()),
        executable.stat().st_size,
        hashlib.sha256(executable.read_bytes()).hexdigest(),
    )
    owner.run_provider_process(
        Runner(),
        [str(executable)],
        provider_args,
        {},
        tmp_path,
        None,
        owner.Control(),
        "kimi",
        expected_executable_binding=expected_binding,
        dialogue=dialogue,
    )

    request, observed_dialogue = observed[0]
    assert request.argv == (str(executable), *provider_args)
    assert request.stdin_bytes is None
    assert request.expected_executable_binding == expected_binding
    assert observed_dialogue is dialogue


def test_kimi_command_resolution_ignores_ambient_binary_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    executable = tmp_path / "kimi.exe"
    executable.write_bytes(b"synthetic")
    monkeypatch.setenv("KIMI_BIN", str(executable))
    assert owner.resolve_provider_command("kimi") is None


def test_kimi_terminal_instruction_and_renderer_share_one_closed_verdict_owner() -> None:
    owner = _load_owner()
    verdicts = getattr(owner, "KIMI_TERMINAL_VERDICTS", ())
    instruction = getattr(owner, "KIMI_AGENT_TERMINAL_INSTRUCTION", b"")

    assert verdicts == ("PASS", "REVISE", "BLOCKED")
    assert instruction == EXPECTED_KIMI_TERMINAL_INSTRUCTION
    for verdict in verdicts:
        form = f"GATE: {verdict}"
        assert instruction.count(form.encode()) == 1
        for decoration in ("", "  ", "\u2022 "):
            match = owner.KIMI_RENDERED_GATE.fullmatch(decoration + form)
            assert match is not None and match.group(1) == verdict


def test_codex_and_claude_generic_prompt_composition_remains_byte_identical() -> None:
    owner = _load_owner()
    caller = b"generic caller bytes"
    expected = (
        owner.EXTERNAL_GOVERNANCE_BEGIN
        + owner.external_governance_capsule_snapshot()
        + owner.EXTERNAL_GOVERNANCE_END
        + caller
    )

    assert tuple(owner.assemble_external_prompt(caller) for _provider in ("codex", "claude")) == (
        expected,
        expected,
    )


@pytest.mark.parametrize(
    "verdict,expected",
    (
        ("PASS", ("completed", "PASS", "COMPLETE:PASS")),
        ("REVISE", ("revise", "REVISE", "COMPLETE:REVISE")),
        ("BLOCKED", ("blocked", "BLOCKED", "COMPLETE:BLOCKED")),
    ),
)
def test_kimi_terminal_accepts_observed_decorated_final_gate(
    tmp_path: Path, verdict: str, expected: tuple[str, str, str]
) -> None:
    owner = _load_owner()

    terminal, result_text = owner.materialize_terminal(
        SimpleNamespace(prompt_path=tmp_path / "result.md"),
        "kimi",
        0,
        1024,
        stdout=f"\u2022 KIMI_WRAPPER_SMOKE=PASS\n  GATE: {verdict}\n\n".encode(),
        stderr=b"",
    )

    assert result_text.endswith(f"  GATE: {verdict}\n\n")
    assert (terminal.status, terminal.gate, terminal.token) == expected


def test_kimi_terminal_allows_prose_with_a_nonleading_gate_reference(
    tmp_path: Path,
) -> None:
    owner = _load_owner()

    terminal, _result_text = owner.materialize_terminal(
        SimpleNamespace(prompt_path=tmp_path / "result.md"),
        "kimi",
        0,
        1024,
        stdout=b"The prior GATE: REVISE is historical prose.\n  GATE: PASS\n",
        stderr=b"",
    )

    assert (terminal.status, terminal.gate, terminal.token) == (
        "completed",
        "PASS",
        "COMPLETE:PASS",
    )


def _kimi_process_result(
    stdout: bytes,
    stderr: bytes,
    *,
    stdout_truncated: bool = False,
    stderr_truncated: bool = False,
    settled: bool = True,
    target_exit_code: int | None = None,
    failure_id: str | None = None,
    dialogue_complete: bool = False,
    outcome: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        outcome=(
            outcome
            if outcome is not None
            else "supervisor-failure"
            if failure_id is not None
            else "success"
        ),
        terminal_stage="capture-limit" if failure_id == "PSV1-CAPTURE-LIMIT" else "completed",
        resources_closed=settled,
        tree=SimpleNamespace(tree_empty=settled, direct_reaped=settled),
        stdin=SimpleNamespace(complete=dialogue_complete),
        stdout=SimpleNamespace(
            truncated=stdout_truncated,
            observed_bytes=len(stdout),
            persisted_bytes=len(stdout),
            digest=hashlib.sha256(stdout).hexdigest(),
        ),
        stderr=SimpleNamespace(
            truncated=stderr_truncated,
            observed_bytes=len(stderr),
            persisted_bytes=len(stderr),
            digest=hashlib.sha256(stderr).hexdigest(),
        ),
        cleanup_issues=(),
        failure_id=failure_id,
        target_exit_code=target_exit_code,
    )


def _public_stdout_metadata(stdout: bytes) -> dict[str, object]:
    empty_digest = hashlib.sha256(b"").hexdigest()
    digest = hashlib.sha256(
        b"provider-capture-v1\x00"
        + hashlib.sha256(stdout).hexdigest().encode("ascii")
        + b"\x00"
        + empty_digest.encode("ascii")
    ).hexdigest()
    return {
        "captureOverflow": False,
        "captureObservedBytes": len(stdout),
        "capturePersistedBytes": len(stdout),
        "captureDigest": digest,
        "captureIssueCount": 0,
    }


def _finalize_kimi(
    owner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    stdout: bytes,
    stderr: bytes,
    process_result: SimpleNamespace | None = None,
    stream: object | None = None,
    with_ledger: bool = False,
    exit_code: int = 0,
    cancelled: bool = False,
    capabilities: object | None = None,
    observed: dict[str, object] | None = None,
    credential_needles: tuple[bytes, ...] = (),
) -> tuple[int, dict[str, object], list[str], object]:
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "user"))
    lifecycle = owner.RunCaptureLifecycle.create("kimi", "safe-public-capture")
    lifecycle.initialize(b"fixture prompt")
    process = process_result or _kimi_process_result(stdout, stderr)
    capture = stream if stream is not None else owner.provider_stream_result(process)
    ledger_calls: list[list[str]] = []
    if with_ledger:
        monkeypatch.setattr(
            owner,
            "run_ledger",
            lambda _runner, arguments: ledger_calls.append(arguments) or True,
        )
        monkeypatch.setattr(
            owner,
            "read_back_external_terminal",
            lambda *_args: {"eventKind": "terminal"},
        )
        control = owner.Control(
            ledger="fixture-item",
            ledger_role="architecture-reviewer",
            ledger_role_explicit=True,
            ledger_lane="fixture-lane",
            ledger_artifact="design.md",
        )
        provenance = owner.ExternalRoleProvenance(
            "architecture-reviewer", "external-reviewer"
        )
    else:
        control = owner.Control()
        provenance = owner.ExternalRoleProvenance("none", "external-reviewer")
    if capabilities is not None:
        control.kimi_capabilities_file = tmp_path / "selected-capabilities.json"
        control.kimi_capabilities = capabilities
    receipt_path = (tmp_path / "kimi-terminal.receipt").resolve()
    control.terminal_receipt = receipt_path
    with owner.TerminalReceiptV1.reserve(receipt_path) as receipt:
        arguments = {
            "cancelled": cancelled,
            "role_provenance": provenance,
            "raw_stdout": stdout,
            "raw_stderr": stderr,
            "process_result": process_result or process,
            "runner": object() if with_ledger else None,
            "credential_needles": credential_needles,
        }
        if observed is not None:
            arguments["kimi_observed"] = observed
        code = owner.finalize_reserved_run_once(
            control,
            "kimi",
            "kimi-code/k3",
            "unsupported",
            "fixture",
            "launch-fixture" if with_ledger else "",
            owner.ReservedExternalRunV1(
                receipt, lifecycle=lifecycle, state="initialized"
            ),
            exit_code,
            capture,
            **arguments,
        )
    payload = owner.parse_provider_result(capsys.readouterr().out)
    notes = (
        ledger_calls[0][ledger_calls[0].index("--notes") + 1]
        if ledger_calls
        else ""
    )
    return code, payload, [notes], lifecycle


def test_kimi_explicit_capability_receipt_is_redacted_and_cleanup_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()
    selected_cwd = tmp_path / "selected-cwd"
    selected_cwd.mkdir()
    capabilities = owner.KimiCapabilitySelectionV1(
        tools=("Read", "Agent"),
        mcp_servers=(
            owner.KimiMcpServerV1(
                name="private-mcp",
                command="fixture",
                args=(),
                env=(owner.KimiNameValueV1("TOKEN", "secret-value"),),
            ),
        ),
        subagents=("*",),
        permission="approve_once",
        cwd=str(selected_cwd),
    )

    code, payload, _notes, lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=b"GATE: PASS\n",
        stderr=b"",
        capabilities=capabilities,
    )

    assert code == 0
    assert payload["selected"] == {
        "tools": ["Read", "Agent"],
        "mcpNames": ["private-mcp"],
        "subagents": ["*"],
        "permission": "approve_once",
        "cwdSelected": True,
    }
    assert payload["observed"] == {"toolCalls": [], "permissionDecisions": []}
    visible = json.dumps(payload)
    assert "secret-value" not in visible
    assert str(selected_cwd) not in visible
    assert not lifecycle.run_dir.exists()


def test_kimi_capture_limit_keeps_real_counters_and_primary_cause(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()
    process = _kimi_process_result(
        b"x",
        b"",
        stdout_truncated=True,
        target_exit_code=0,
        failure_id="PSV1-CAPTURE-LIMIT",
    )
    process.stdout.observed_bytes = 1261818
    process.stdout.persisted_bytes = 1048576
    process.stdout.digest = "a" * 64
    stream = owner.provider_stream_result(process)

    code, payload, _notes, lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=b"GATE: PASS\n",
        stderr=b"",
        process_result=process,
        stream=stream,
        exit_code=1,
    )

    assert code == 1
    assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_OUTPUT_SCAN_UNAVAILABLE"
    assert payload["resultText"] == ""
    assert {
        "captureOverflow": payload["captureOverflow"],
        "captureObservedBytes": payload["captureObservedBytes"],
        "capturePersistedBytes": payload["capturePersistedBytes"],
        "captureDigest": payload["captureDigest"],
        "captureIssueCount": payload["captureIssueCount"],
    } == {
        "captureOverflow": True,
        "captureObservedBytes": 1261818,
        "capturePersistedBytes": 1048576,
        "captureDigest": stream.digest,
        "captureIssueCount": 1,
    }
    assert payload["primaryOutcome"] == {
        "exitCode": 1,
        "token": "FAILED:capture-overflow",
        "status": "blocked",
        "gate": "none",
        "note": "stream: combined stdout/stderr capture exceeded configured maximum; observedBytes=1261818",
    }
    assert payload["cleanupStatus"] == "complete"
    assert not lifecycle.run_dir.exists()


def test_kimi_complete_stdout_overflow_returns_bounded_scanned_answer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()
    process = _kimi_process_result(
        b"x",
        b"",
        stdout_truncated=True,
        target_exit_code=0,
        dialogue_complete=True,
        outcome="success",
    )
    process.stdout.observed_bytes = 1261818
    process.stdout.persisted_bytes = 1048576
    process.stdout.digest = "a" * 64
    stream = owner.provider_stream_result(process)

    code, payload, _notes, lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=b"GATE: PASS\n",
        stderr=b"",
        process_result=process,
        stream=stream,
        exit_code=0,
    )

    assert code == 0
    assert payload["resultText"] == "GATE: PASS\n"
    assert payload["token"] == "COMPLETE:EXTERNAL_NONAUTHORIZING"
    assert payload["captureOverflow"] is True
    assert payload["captureObservedBytes"] == 1261818
    assert payload["primaryOutcome"]["token"] == "COMPLETE:PASS"
    assert payload["cleanupStatus"] == "complete"
    assert not lifecycle.run_dir.exists()


def test_kimi_complete_stdout_overflow_still_blocks_secret_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()
    process = _kimi_process_result(
        b"x",
        b"",
        stdout_truncated=True,
        target_exit_code=0,
        dialogue_complete=True,
        outcome="success",
    )
    stream = owner.provider_stream_result(process)

    code, payload, _notes, lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=b"secret-canary\nGATE: PASS\n",
        stderr=b"",
        process_result=process,
        stream=stream,
        exit_code=0,
        credential_needles=(b"secret-canary",),
    )

    assert code != 0
    assert payload["resultText"] == ""
    assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
    assert payload["primaryOutcome"]["token"] == (
        "UNVERIFIED:E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
    )
    assert "secret-canary" not in json.dumps(payload)
    assert not lifecycle.run_dir.exists()


def test_kimi_explicit_receipt_includes_only_bounded_observed_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()
    capabilities = owner.KimiCapabilitySelectionV1(tools=("Read",))
    observed = {
        "toolCalls": [
            {"id": "1:tool-call-1", "title": "Read", "status": "completed"}
        ],
        "permissionDecisions": [
            {"id": "1:tool-call-1", "title": "Read", "decision": "reject"}
        ],
    }
    try:
        code, payload, _notes, lifecycle = _finalize_kimi(
            owner,
            tmp_path,
            monkeypatch,
            capsys,
            stdout=b"GATE: PASS\n",
            stderr=b"",
            capabilities=capabilities,
            observed=observed,
        )
    except TypeError as exc:
        pytest.fail(f"Kimi observed evidence did not reach the finalizer: {exc}")

    assert code == 0
    assert payload["observed"] == observed
    assert set(payload["observed"]) == {"toolCalls", "permissionDecisions"}
    assert not lifecycle.run_dir.exists()


def test_kimi_selected_receipt_budget_rejects_before_receipt_or_provider_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()
    capabilities_file = tmp_path / "large-valid-capabilities.json"
    _write_kimi_capabilities(
        capabilities_file,
        tools=[f"tool-{index:04d}-{'x' * 96}" for index in range(4096)],
    )
    selection = owner.read_kimi_capability_selection(capabilities_file)
    assert capabilities_file.stat().st_size <= owner.PROMPT_SNAPSHOT_MAX_BYTES
    control = owner.Control(
        terminal_receipt=tmp_path / "must-not-reserve.receipt",
        kimi_capabilities_file=capabilities_file,
        kimi_capabilities=selection,
    )
    prevalidated = owner.PolicyBoundLaunch(
        control,
        "fixture",
        (),
        "kimi-code/k3",
        "unsupported",
        owner.ExternalRoleProvenance("none", "none"),
        None,
    )
    monkeypatch.setattr(
        owner,
        "_prevalidate_policy_bound_external_launch",
        lambda _provider, _argv: prevalidated,
    )
    monkeypatch.setattr(
        owner.TerminalReceiptV1,
        "reserve",
        classmethod(
            lambda *_args, **_kwargs: pytest.fail(
                "oversized selected receipt reached reservation"
            )
        ),
    )
    monkeypatch.setattr(
        owner,
        "_resolve_launch_provider_command",
        lambda *_args: pytest.fail("oversized selected receipt reached provider start"),
    )
    monkeypatch.setattr(owner, "os", SimpleNamespace(name="nt"))

    assert owner.launch("kimi", ["fixture"]) == 1
    assert "E_KIMI_RECEIPT_BUDGET" in capsys.readouterr().err


def test_kimi_receipt_budget_has_exact_minimum_and_one_over_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _load_owner()
    selected = owner.kimi_selected_receipt(owner.KimiCapabilitySelectionV1())
    empty = owner.empty_kimi_observed_receipt()
    omitted = {**empty, "observationsOmitted": True}
    exact_limit = len(owner._kimi_receipt_json({"selected": selected, "observed": omitted}))

    monkeypatch.setattr(owner, "AGENT_RUN_MAX_LINE_CHARS", exact_limit)
    remaining = owner.kimi_observed_receipt_budget(selected)

    assert remaining == len(owner._kimi_receipt_json(empty))
    monkeypatch.setattr(owner, "AGENT_RUN_MAX_LINE_CHARS", exact_limit - 1)
    with pytest.raises(ValueError, match="^E_KIMI_RECEIPT_BUDGET$"):
        owner.kimi_observed_receipt_budget(selected)


def test_kimi_observed_receipt_uses_incremental_budget_and_marks_real_omission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()
    title = "Read ASCII " + "\u00e9" * 24 + " \U0001f680"
    longer_title = title + " updated " + "\u00df" * 20
    short_title = "Read concise"
    update = {
        "sessionUpdate": "tool_call",
        "toolCallId": "tool-1",
        "title": title,
        "status": "in_progress",
    }
    longer_update = {
        "sessionUpdate": "tool_call_update",
        "toolCallId": "tool-1",
        "title": longer_title,
    }
    short_update = {
        "sessionUpdate": "tool_call_update",
        "toolCallId": "tool-1",
        "title": short_title,
        "status": "completed",
    }
    permission = _permission_request(
        [{"optionId": "deny-custom", "name": "Reject", "kind": "reject_once"}]
    )
    permission["toolCall"] = {"toolCallId": "tool-1", "title": title}

    class _Channel:
        def write_line(self, payload: bytes) -> int:
            return len(payload)

    unbounded = owner.KimiAcpOneShotV1(b"safe task", str(tmp_path))
    unbounded._record_tool_update(update)
    unbounded._record_tool_update(longer_update)
    longest_observed_chars = len(owner._kimi_receipt_json(unbounded.observed_receipt()))
    unbounded._record_tool_update(short_update)
    object.__setattr__(unbounded, "session_id", "session-1")
    unbounded._handle_permission_request(
        _Channel(), {"id": 1, "params": {"sessionId": "session-1", "options": permission["options"], "toolCall": permission["toolCall"]}}, collect=True
    )
    expected = unbounded.observed_receipt()
    empty = owner.empty_kimi_observed_receipt()
    omission_allowance = (
        len(owner._kimi_receipt_json({**empty, "observationsOmitted": True}))
        - len(owner._kimi_receipt_json(empty))
    )
    selected = owner.kimi_selected_receipt(
        owner.KimiCapabilitySelectionV1(tools=("Read",))
    )
    retained_budget = max(
        longest_observed_chars,
        len(owner._kimi_receipt_json(expected)),
    )
    selected_overhead = len(
        owner._kimi_receipt_json({"selected": selected, "observed": empty})
    ) - len(owner._kimi_receipt_json(empty))
    monkeypatch.setattr(
        owner,
        "AGENT_RUN_MAX_LINE_CHARS",
        selected_overhead + retained_budget + omission_allowance,
    )
    budget = owner.kimi_observed_receipt_budget(selected)
    assert budget == retained_budget
    exchange = owner.KimiAcpOneShotV1(
        b"safe task", str(tmp_path), observed_budget_chars=budget
    )
    object.__setattr__(exchange, "session_id", "session-1")
    for item in (update, longer_update, short_update):
        exchange._record_tool_update(item)
        assert exchange._observed_serialized_chars == len(
            owner._kimi_receipt_json(exchange.observed_receipt())
        )
    exchange._handle_permission_request(
        _Channel(), {"id": 1, "params": {"sessionId": "session-1", "options": permission["options"], "toolCall": permission["toolCall"]}}, collect=True
    )
    assert exchange.observed_receipt() == expected
    assert exchange._observed_serialized_chars == len(
        owner._kimi_receipt_json(exchange.observed_receipt())
    )

    exchange._record_tool_update(
        {
            "sessionUpdate": "tool_call",
            "toolCallId": "tool-2",
            "title": "Read " + "long-ascii-" * 80 + "\u00e9\U0001f680",
            "status": "in_progress",
        }
    )
    observed = exchange.observed_receipt()
    assert observed["observationsOmitted"] is True
    assert observed["toolCalls"] == expected["toolCalls"]
    assert observed["permissionDecisions"] == expected["permissionDecisions"]
    assert len(owner._kimi_receipt_json(observed)) == (
        exchange._observed_serialized_chars + omission_allowance
    )
    assert len(owner._kimi_receipt_json(observed)) <= budget + omission_allowance

    capabilities = owner.KimiCapabilitySelectionV1(tools=("Read",))
    code, payload, _notes, lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=b"artifact\nGATE: PASS\n",
        stderr=b"",
        capabilities=capabilities,
        observed=observed,
    )
    assert code == 0
    assert payload["resultText"] == "artifact\nGATE: PASS\n"
    assert payload["observed"]["observationsOmitted"] is True
    assert len(
        owner._kimi_receipt_json(
            {"selected": selected, "observed": payload["observed"]}
        )
    ) <= owner.AGENT_RUN_MAX_LINE_CHARS
    assert not lifecycle.run_dir.exists()


@pytest.mark.parametrize(
    ("provider", "model", "effort"),
    (
        ("kimi", "kimi-code/k3", "unsupported"),
        ("codex", "gpt-5.6-sol", "xhigh"),
        ("claude", "opus", "xhigh"),
    ),
)
def test_legacy_provider_receipts_parse_without_kimi_capability_fields(
    provider: str, model: str, effort: str
) -> None:
    owner = _load_owner()
    outcome = owner.FinalOutcome(
        0,
        "COMPLETE:EXTERNAL_NONAUTHORIZING",
        "passed",
        "PASS",
        "fixture",
        0,
        "COMPLETE:PASS",
        "passed",
        "PASS",
        "fixture",
        "complete",
        0,
        "",
        False,
        0,
    )

    payload = owner.parse_provider_result(
        owner.build_provider_result_line(
            provider,
            model,
            effort,
            "GATE: PASS\n",
            outcome,
            cancelled=False,
            timed_out=False,
            role_provenance=owner.ExternalRoleProvenance("none", "none"),
        )
    )

    assert "selected" not in payload
    assert "observed" not in payload


def test_provider_result_parser_rejects_malformed_or_non_kimi_capability_fields() -> None:
    owner = _load_owner()
    outcome = owner.FinalOutcome(
        0,
        "COMPLETE:EXTERNAL_NONAUTHORIZING",
        "passed",
        "PASS",
        "fixture",
        0,
        "COMPLETE:PASS",
        "passed",
        "PASS",
        "fixture",
        "complete",
        0,
        "",
        False,
        0,
    )
    base = owner.build_provider_result_line(
        "kimi",
        "kimi-code/k3",
        "unsupported",
        "GATE: PASS\n",
        outcome,
        cancelled=False,
        timed_out=False,
        role_provenance=owner.ExternalRoleProvenance("none", "none"),
    )
    prefix, encoded = base.rstrip("\n").split("=", 1)
    assert prefix == "ORCHESTRARIUM_PROVIDER_RESULT_V2"
    payload = json.loads(encoded)
    selected = {
        "tools": ["Read"],
        "mcpNames": [],
        "subagents": [],
        "permission": "reject",
        "cwdSelected": False,
    }
    observed = {"toolCalls": [], "permissionDecisions": []}
    malformed = []
    for changes in (
        {"selected": selected},
        {"selected": {**selected, "tools": [{}]}, "observed": observed},
        {
            "provider": "claude",
            "model": "opus",
            "effort": "xhigh",
            "selected": selected,
            "observed": observed,
        },
        {
            "selected": selected,
            "observed": {
                "toolCalls": [
                    {"id": "duplicate", "title": "Read", "status": "completed"},
                    {"id": "duplicate", "title": "Read", "status": "failed"},
                ],
                "permissionDecisions": [],
            },
        },
        {
            "selected": selected,
            "observed": {**observed, "observationsOmitted": False},
        },
        {
            "selected": selected,
            "observed": {**observed, "observationsOmitted": "true"},
        },
        {
            "selected": selected,
            "observed": {**observed, "unexpected": True},
        },
    ):
        changed = {**payload, **changes}
        malformed.append(
            owner.RESULT_PREFIX
            + json.dumps(changed, ensure_ascii=True, separators=(",", ":"))
            + "\n"
        )

    for line in malformed:
        with pytest.raises(
            ValueError, match="^provider result Kimi capability evidence mismatch$"
        ):
            owner.parse_provider_result(line)


@pytest.mark.parametrize(
    ("verdict", "expected_exit"),
    (("PASS", 0), ("REVISE", 0), ("BLOCKED", 1)),
)
def test_valid_kimi_verdicts_remain_external_nonauthorizing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    verdict: str,
    expected_exit: int,
) -> None:
    owner = _load_owner()
    code, payload, _notes, lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=f"GATE: {verdict}\n".encode(),
        stderr=b"",
        with_ledger=True,
    )

    assert code == expected_exit
    assert payload["gate"] == verdict
    assert payload["authorizing"] is False
    assert payload["closesRunIds"] == []
    assert payload["terminalClass"] == "external-nonauthorizing"
    assert not lifecycle.run_dir.exists()


def _finalize_kimi_child_nonzero(
    owner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stderr: bytes,
    *,
    with_ledger: bool = True,
    failure_id: str | None = None,
    cancelled: bool = False,
) -> tuple[int, dict[str, object], list[str], object]:
    stdout = b"  GATE: PASS\n"
    process = _kimi_process_result(
        stdout, stderr, target_exit_code=23, failure_id=failure_id
    )
    return _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=stdout,
        stderr=stderr,
        process_result=process,
        with_ledger=with_ledger,
        exit_code=23,
        cancelled=cancelled,
    )


@pytest.mark.parametrize(
    ("stderr", "category"),
    (
        (b"  provider.rate_limit \n", "rate_limit"),
        (b"auth.login_required", "auth"),
        (b"provider.auth_error", "auth"),
        (b"provider.overloaded", "vendor"),
        (b"provider.connection_error", "vendor"),
        (b"error: unknown command kimi", "invocation"),
        (b"error: unknown option --agent-file", "invocation"),
    ),
)
def test_kimi_settled_child_nonzero_exposes_only_closed_category(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stderr: bytes,
    category: str,
) -> None:
    """Catches collapsed genuine Kimi child refusals after safety scanning."""

    owner = _load_owner()
    code, payload, notes, lifecycle = _finalize_kimi_child_nonzero(
        owner, tmp_path, monkeypatch, capsys, stderr
    )

    assert code == 23
    assert (payload["token"], payload["status"], payload["gate"]) == (
        "FAILED:nonzero-exit",
        "blocked",
        "none",
    )
    assert payload["childNonzeroCategory"] == category
    assert payload["primaryOutcome"]["childNonzeroCategory"] == category
    assert f"childNonzeroCategory={category}" in notes[0]
    assert stderr.decode("utf-8") not in json.dumps({"payload": payload, "notes": notes})
    assert not lifecycle.run_dir.exists()


@pytest.mark.parametrize(
    "stderr",
    (
        b"provider.api_error quota login 429 401 403 server",
        b"provider.rate_limit provider.auth_error",
        b"evilprovider.rate_limit",
        b"provider.rate_limit_evil",
        b"https://example.invalid/provider.rate_limit",
        b"prose containing provider.rate_limit",
        b"\xffprovider.rate_limit",
        b"provider.rate_limit\x00",
    ),
)
def test_kimi_child_nonzero_refusal_text_outside_exact_patterns_is_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stderr: bytes,
) -> None:
    """Catches broad text heuristics or malformed stderr classification."""

    owner = _load_owner()
    code, payload, notes, _lifecycle = _finalize_kimi_child_nonzero(
        owner, tmp_path, monkeypatch, capsys, stderr
    )

    assert code == 23
    assert payload["childNonzeroCategory"] == "unknown"
    assert payload["primaryOutcome"]["childNonzeroCategory"] == "unknown"
    assert "childNonzeroCategory=unknown" in notes[0]


def test_kimi_same_refusal_category_has_identical_public_capture_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Catches public metadata that acts as an oracle for hidden refusal text."""

    owner = _load_owner()
    first = _finalize_kimi_child_nonzero(
        owner,
        tmp_path / "first",
        monkeypatch,
        capsys,
        b"provider.rate_limit\nunrelated first detail",
    )[1]
    second = _finalize_kimi_child_nonzero(
        owner,
        tmp_path / "second",
        monkeypatch,
        capsys,
        b"provider.rate_limit\nunrelated second detail",
    )[1]
    public_keys = (
        "token",
        "status",
        "gate",
        "captureOverflow",
        "captureObservedBytes",
        "capturePersistedBytes",
        "captureDigest",
        "captureIssueCount",
        "childNonzeroCategory",
    )

    assert {key: first[key] for key in public_keys} == {
        key: second[key] for key in public_keys
    }


def test_kimi_exit_zero_ignores_refusal_looking_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Catches a refusal classifier that changes a successful Kimi terminal."""

    owner = _load_owner()
    code, payload, _notes, _lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=b"  GATE: PASS\n",
        stderr=b"provider.rate_limit",
    )

    assert code == 0
    assert payload["gate"] == "PASS"
    assert "childNonzeroCategory" not in payload


def test_kimi_empty_credential_needles_block_machine_path_before_result_materialization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Catches Kimi output scanning being incorrectly gated on credential needles."""

    owner = _load_owner()
    machine_path = b"C:" + br"\Users\private-machine\secret.txt"
    stdout = machine_path + b"\n  GATE: PASS\n"

    code, payload, _notes, lifecycle = _finalize_kimi(
        owner, tmp_path, monkeypatch, capsys, stdout=stdout, stderr=b""
    )

    assert code != 0
    assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_MACHINE_PATH_ECHO"
    assert payload["resultText"] == ""
    assert machine_path.decode("ascii") not in json.dumps(payload)
    assert not lifecycle.run_dir.exists()


def test_kimi_empty_credential_needles_allow_safe_settled_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Catches the Kimi output scan rejecting a settled output with no unsafe path."""

    owner = _load_owner()
    stdout = b"review complete\n  GATE: PASS\n"

    code, payload, _notes, lifecycle = _finalize_kimi(
        owner, tmp_path, monkeypatch, capsys, stdout=stdout, stderr=b""
    )

    assert code == 0
    assert payload["gate"] == "PASS"
    assert payload["resultText"] == stdout.decode("ascii")
    assert not lifecycle.run_dir.exists()


def test_kimi_empty_credential_needles_fail_closed_when_raw_streams_are_unsettled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Catches Kimi materialization before both complete raw streams are settled."""

    owner = _load_owner()
    stdout = b"review complete\n  GATE: PASS\n"
    process = _kimi_process_result(stdout, b"", settled=False)

    code, payload, _notes, lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=stdout,
        stderr=b"",
        process_result=process,
    )

    assert code != 0
    assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_OUTPUT_SCAN_UNAVAILABLE"
    assert payload["resultText"] == ""
    assert not lifecycle.run_dir.exists()


@pytest.mark.parametrize(
    "stderr",
    (
        b"C:" + br"\Users\synthetic-stderr-one\private.txt\n",
        b"C:" + br"\Users\synthetic-stderr-two\private.txt\n",
    ),
)
def test_kimi_benign_stderr_machine_path_has_stdout_only_public_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stderr: bytes,
) -> None:
    """Catches public Kimi metadata that commits to a benign stderr-only path."""

    owner = _load_owner()
    stdout = b"\xe2\x80\xa2 KIMI_WRAPPER_SMOKE=PASS\n  GATE: PASS\n"
    code, payload, notes, lifecycle = _finalize_kimi(
        owner, tmp_path, monkeypatch, capsys, stdout=stdout, stderr=stderr, with_ledger=True
    )

    assert code == 0
    assert payload["gate"] == "PASS"
    assert {key: payload[key] for key in _public_stdout_metadata(stdout)} == _public_stdout_metadata(stdout)
    visible_terminal = json.dumps({"payload": payload, "notes": notes})
    assert stderr.decode("utf-8").strip() not in visible_terminal
    assert not lifecycle.run_dir.exists()


def test_kimi_error_marker_keeps_nonpass_without_stderr_capture_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Catches an ERROR verdict that reintroduces a stderr digest or byte oracle."""

    owner = _load_owner()
    stdout = b"  GATE: PASS\n"
    sentinel = b"stderr-only-sentinel"
    code, payload, notes, lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=stdout,
        stderr=b"ERROR: " + sentinel,
        with_ledger=True,
    )

    assert code == 1
    assert payload["token"] == "UNVERIFIED:err-markers"
    assert payload["gate"] == "none"
    assert payload["primaryOutcome"]["token"] == "UNVERIFIED:err-markers"
    assert {key: payload[key] for key in _public_stdout_metadata(stdout)} == _public_stdout_metadata(stdout)
    assert sentinel.decode("utf-8") not in json.dumps({"payload": payload, "notes": notes})
    assert not lifecycle.run_dir.exists()


def test_generic_capture_metadata_remains_exactly_as_supplied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Catches a Kimi-only projection that changes generic provider capture fields."""

    owner = _load_owner()
    root = (tmp_path / "claude-captures").resolve()
    monkeypatch.setenv("CLAUDE_PROMPTS_DIR", str(root))
    lifecycle = owner.RunCaptureLifecycle.create("claude", "generic-capture-golden")
    lifecycle.initialize(b"fixture prompt")
    stream = owner.StreamCaptureResult(False, 17, 13, "a" * 64, ("fixture",))

    receipt_path = (tmp_path / "generic-terminal.receipt").resolve()
    with owner.TerminalReceiptV1.reserve(receipt_path) as receipt:
        code = owner.finalize_reserved_run_once(
            owner.Control(terminal_receipt=receipt_path),
            "claude",
            "opus",
            "xhigh",
            "fixture",
            "",
            owner.ReservedExternalRunV1(
                receipt, lifecycle=lifecycle, state="initialized"
            ),
            0,
            stream,
            role_provenance=owner.ExternalRoleProvenance("none", "external-reviewer"),
            raw_stdout=b"GATE: PASS\n",
            raw_stderr=b"",
        )
    payload = owner.parse_provider_result(capsys.readouterr().out)

    assert code == 0
    assert {
        "captureOverflow": payload["captureOverflow"],
        "captureObservedBytes": payload["captureObservedBytes"],
        "capturePersistedBytes": payload["capturePersistedBytes"],
        "captureDigest": payload["captureDigest"],
        "captureIssueCount": payload["captureIssueCount"],
    } == {
        "captureOverflow": False,
        "captureObservedBytes": 17,
        "capturePersistedBytes": 13,
        "captureDigest": "a" * 64,
        "captureIssueCount": 1,
    }
    assert "childNonzeroCategory" not in payload


@pytest.mark.parametrize(
    "stdout",
    (
        b"natural language without a gate\n",
        b"GATE: PASS\ntrailing prose\n",
        b"  GATE: MAYBE\n  GATE: PASS\n",
        b"    GATE: REVISE\n  GATE: PASS\n",
        b"GATE : REVISE\n  GATE: PASS\n",
        b"  GATE: PASS\n  GATE: PASS\n",
        b"  GATE: PASS\n  GATE: REVISE\n",
        b"  GATE: PASS\n  GATE: BLOCKED\n",
        b"    GATE: PASS\n",
    ),
)
def test_kimi_terminal_rejects_nonfinal_or_conflicting_decorated_gates(
    tmp_path: Path, stdout: bytes
) -> None:
    owner = _load_owner()

    terminal, _result_text = owner.materialize_terminal(
        SimpleNamespace(prompt_path=tmp_path / "result.md"),
        "kimi",
        0,
        1024,
        stdout=stdout,
        stderr=b"",
    )

    assert (terminal.status, terminal.gate, terminal.token) == (
        "blocked",
        "none",
        "UNVERIFIED:no-gate-line",
    )


def test_generic_terminal_does_not_accept_kimi_renderer_decoration(tmp_path: Path) -> None:
    owner = _load_owner()

    terminal, _result_text = owner.materialize_terminal(
        SimpleNamespace(prompt_path=tmp_path / "result.md"),
        "claude",
        0,
        1024,
        stdout=b"\xe2\x80\xa2 KIMI_WRAPPER_SMOKE=PASS\n  GATE: PASS\n",
        stderr=b"",
    )

    assert (terminal.status, terminal.gate, terminal.token) == (
        "blocked",
        "none",
        "UNVERIFIED:no-gate-line",
    )


def test_kimi_auth_is_cli_owned_without_config_or_credential_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    user_home = tmp_path / "user"
    user_home.mkdir()
    original_read_bytes = owner.Path.read_bytes
    original_read_text = owner.Path.read_text

    def reject_kimi_auth_read(path: Path, *args, **kwargs):
        if ".kimi-code" in path.parts:
            pytest.fail(f"wrapper read Kimi-owned auth path: {path.name}")
        return original_read_bytes(path, *args, **kwargs)

    def reject_kimi_auth_text_read(path: Path, *args, **kwargs):
        if ".kimi-code" in path.parts:
            pytest.fail(f"wrapper read Kimi-owned auth path: {path.name}")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(owner.Path, "read_bytes", reject_kimi_auth_read)
    monkeypatch.setattr(owner.Path, "read_text", reject_kimi_auth_text_read)
    configuration = owner.resolve_provider_auth_configuration(
        "kimi",
        {
            "USERPROFILE": str(user_home),
            "PATH": "provider-path",
            "KIMI_CODE_HOME": "ambient-home-must-not-forward",
        },
    )

    assert configuration.mode == "kimi-user-session"
    assert configuration.needles == ()
    assert configuration.child_environment["USERPROFILE"] == str(user_home)
    assert configuration.child_environment["PATH"] == "provider-path"
    assert configuration.child_environment["KIMI_CODE_EXPERIMENTAL_FLAG"] == "1"
    assert configuration.child_environment["KIMI_CODE_NO_AUTO_UPDATE"] == "1"
    assert configuration.child_environment["DO_NOT_TRACK"] == "1"
    assert "KIMI_CODE_HOME" not in configuration.child_environment
    assert not (user_home / ".kimi-code").exists()


def test_kimi_mcp_credential_needles_cover_opaque_values_and_structured_credentials() -> None:
    owner = _load_owner()
    assert _SYNTHETIC_AUTH_VALUE.encode("ascii") == (
        b"Bear" + b"er bearer-" + b"payload"
    )
    selection = owner.KimiCapabilitySelectionV1(
        mcp_servers=(
            owner.KimiMcpServerV1(
                name="local",
                command="fixture",
                args=(
                    "--api-token", "argument-token",
                    "--client-secret=inline%2Dsecret",
                    "--mode", "public-mode",
                ),
                env=(
                    owner.KimiNameValueV1("API_TOKEN", "env-token"),
                    owner.KimiNameValueV1("PRIVATE_KEY", "private-key"),
                    owner.KimiNameValueV1("PASSWORD", "password-value"),
                    owner.KimiNameValueV1("PATH", "public-path"),
                    owner.KimiNameValueV1("LANG", "public-lang"),
                    owner.KimiNameValueV1("TIMEOUT", "public-timeout"),
                ),
            ),
            owner.KimiMcpServerV1(
                name="remote",
                transport="http",
                url="https://example.invalid/mcp",
                headers=(
                    owner.KimiNameValueV1("Authorization", _SYNTHETIC_AUTH_VALUE),
                    owner.KimiNameValueV1("Proxy-Authorization", "Basic basic-payload"),
                    owner.KimiNameValueV1("Cookie", "sid=cookie-value; theme=public-theme"),
                    owner.KimiNameValueV1("Accept-Language", "public-language"),
                    owner.KimiNameValueV1("X-Region", "public-region"),
                    owner.KimiNameValueV1("X-Timeout", "public-header-timeout"),
                ),
            ),
        )
    )

    needles = owner._kimi_mcp_credential_needles(selection)

    assert set(needles) == {
        b"env-token", b"private-key", b"password-value",
        b"argument-token", b"inline%2Dsecret", b"inline-secret",
        _SYNTHETIC_AUTH_VALUE.encode("ascii"),
        _SYNTHETIC_AUTH_PAYLOAD.encode("ascii"),
        b"Basic basic-payload", b"basic-payload",
        b"sid=cookie-value; theme=public-theme", b"cookie-value", b"public-theme",
    }
    assert len(needles) == len(set(needles))


def test_kimi_mcp_argument_options_and_carriers_protect_credentials() -> None:
    owner = _load_owner()
    selection = owner.KimiCapabilitySelectionV1(
        mcp_servers=(
            owner.KimiMcpServerV1(
                name="fixture",
                command="fixture",
                args=(
                    "/api-token:slash-colon-secret",
                    "--api-token:dash-colon-secret",
                    "--aws-secret-access-key", "compound-secret",
                    "--endpoint=https://url-user:url-pass@example.invalid/"
                    "private%2Dsegment?token=query%2Dsecret#fragment%2Dsecret",
                    "--header", "Authorization: " + _SYNTHETIC_AUTH_SCHEME + " header-" + "secret",
                    "-H", "Proxy-Authorization: Basic proxy-secret",
                    "--header=Cookie: sid=cookie-secret; theme=private-theme",
                    "--header", "X-Custom-Header: private-header",
                    "--env", "API_TOKEN=env-secret",
                    "-e", "CUSTOM_SETTING=private-env",
                ),
            ),
        )
    )

    needles = set(owner._kimi_mcp_credential_needles(selection))

    assert {
        b"slash-colon-secret", b"dash-colon-secret", b"compound-secret",
        b"url-user", b"url-pass", b"private%2Dsegment", b"private-segment",
        b"query%2Dsecret", b"query-secret",
        b"fragment%2Dsecret", b"fragment-secret",
        b"header-secret", b"proxy-secret", b"cookie-secret", b"private-theme",
        b"private-header", b"env-secret", b"private-env",
    } <= needles
    assert b"example.invalid" not in needles
    assert b"--endpoint=https:" not in needles


def test_kimi_mcp_argument_parser_preserves_public_controls() -> None:
    owner = _load_owner()
    selection = owner.KimiCapabilitySelectionV1(
        mcp_servers=(
            owner.KimiMcpServerV1(
                name="fixture",
                command="fixture",
                args=(
                    "--port", "8080",
                    "--mode", "public-mode",
                    "--endpoint=https://example.invalid/mcp",
                    "--header", "Accept-Language: en",
                    "-H", "X-Region: eu",
                    "--env", "PATH=/usr/bin",
                    "-e", "TIMEOUT=30",
                ),
            ),
        )
    )

    assert owner._kimi_mcp_credential_needles(selection) == ()


def test_kimi_mcp_credential_needles_have_finite_unique_count() -> None:
    owner = _load_owner()

    def selection(count: int):
        return owner.KimiCapabilitySelectionV1(
            mcp_servers=(
                owner.KimiMcpServerV1(
                    name="fixture",
                    command="fixture",
                    args=tuple(f"private-value-{index}" for index in range(count)),
                ),
            )
        )

    assert len(owner._kimi_mcp_credential_needles(selection(256))) == 256
    with pytest.raises(
        ValueError, match="^E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE$"
    ):
        owner._kimi_mcp_credential_needles(selection(257))


def test_kimi_mcp_argument_values_default_private_except_public_controls() -> None:
    owner = _load_owner()
    selection = owner.KimiCapabilitySelectionV1(
        mcp_servers=(
            owner.KimiMcpServerV1(
                name="fixture",
                command="fixture",
                args=(
                    "--auth", "opaque-secret",
                    "--dash-auth", "-dash-private",
                    "--slash-auth", "/slash-private",
                    "--custom-setting=inline-private",
                    "positional-private",
                    "--header-list", "Authorization: " + _SYNTHETIC_AUTH_SCHEME + " list-" + "secret",
                    "--environment-variables", "CUSTOM=env-list-secret",
                    "--port", "8080",
                    "--mode", "public-mode",
                    "--endpoint", "https://example.invalid/mcp",
                ),
            ),
        )
    )

    needles = set(owner._kimi_mcp_credential_needles(selection))

    assert {
        b"opaque-secret",
        b"-dash-private",
        b"/slash-private",
        b"inline-private",
        b"positional-private",
        b"list-secret",
        b"env-list-secret",
    } <= needles
    assert {b"8080", b"public-mode", b"example.invalid"}.isdisjoint(needles)


@pytest.mark.parametrize(
    "canary",
    (
        b"env-token",
        b"private-key",
        b"password-value",
        b"argument-token",
        b"inline-secret",
        _SYNTHETIC_AUTH_PAYLOAD.encode("ascii"),
        b"basic-payload",
        b"cookie-value",
    ),
)
def test_kimi_mcp_credential_echo_is_removed_from_success_and_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    canary: bytes,
) -> None:
    owner = _load_owner()
    selection = owner.KimiCapabilitySelectionV1(
        mcp_servers=(
            owner.KimiMcpServerV1(
                name="local",
                command="fixture",
                args=(
                    "--api-token", "argument-token",
                    "--client-secret=inline%2Dsecret",
                ),
                env=(
                    owner.KimiNameValueV1("API_TOKEN", "env-token"),
                    owner.KimiNameValueV1("PRIVATE_KEY", "private-key"),
                    owner.KimiNameValueV1("PASSWORD", "password-value"),
                ),
            ),
            owner.KimiMcpServerV1(
                name="remote",
                transport="http",
                url="https://example.invalid/mcp",
                headers=(
                    owner.KimiNameValueV1("Authorization", _SYNTHETIC_AUTH_VALUE),
                    owner.KimiNameValueV1("Proxy-Authorization", "Basic basic-payload"),
                    owner.KimiNameValueV1("Cookie", "sid=cookie-value"),
                ),
            ),
        )
    )
    needles = owner._merge_credential_needles(
        (), owner._kimi_mcp_credential_needles(selection)
    )

    code, payload, _notes, lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=canary + b"\nGATE: PASS\n",
        stderr=b"",
        capabilities=selection,
        credential_needles=needles,
    )

    visible = json.dumps(payload)
    assert code != 0
    assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
    assert canary.decode("ascii") not in visible
    assert canary.decode("ascii") not in (
        tmp_path / "kimi-terminal.receipt"
    ).read_text(encoding="utf-8")
    assert not lifecycle.run_dir.exists()


def test_kimi_mcp_ordinary_arguments_remain_public() -> None:
    owner = _load_owner()
    selection = owner.KimiCapabilitySelectionV1(
        mcp_servers=(
            owner.KimiMcpServerV1(
                name="local",
                command="fixture",
                args=("--port", "8080", "--mode", "public-mode"),
            ),
        )
    )

    assert owner._kimi_mcp_credential_needles(selection) == ()


def test_kimi_mcp_credential_echo_keeps_nonzero_result_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()
    selection = owner.KimiCapabilitySelectionV1(
        mcp_servers=(
            owner.KimiMcpServerV1(
                name="local",
                command="fixture",
                args=(),
                env=(owner.KimiNameValueV1("TOKEN", "nonzero-token"),),
            ),
        )
    )
    code, payload, _notes, lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=b"nonzero-token\nGATE: PASS\n",
        stderr=b"",
        exit_code=23,
        capabilities=selection,
        credential_needles=owner._merge_credential_needles(
            (), owner._kimi_mcp_credential_needles(selection)
        ),
    )

    assert code == 23
    assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
    assert "nonzero-token" not in json.dumps(payload)
    assert "nonzero-token" not in (tmp_path / "kimi-terminal.receipt").read_text(
        encoding="utf-8"
    )
    assert not lifecycle.run_dir.exists()


def test_kimi_wrapper_has_no_auth_storage_contract() -> None:
    source = OWNER_PATH.read_text(encoding="utf-8")
    forbidden = (
        "_kimi_sanitized_runtime_home",
        "access_token",
        "refresh_token",
        "expires_at",
        "oauth_host",
        "E_KIMI_AUTH_STORAGE_INVALID",
    )
    assert all(token not in source for token in forbidden)


def test_kimi_profile_identifier_has_one_production_owner() -> None:
    owner = _load_owner()
    source = (ROOT / "scripts" / "process_supervision" / "process_runner.py").read_text(
        encoding="utf-8"
    )
    assert owner.KIMI_WINDOWS_PROFILE_V1.profile_id == "kimi-acp-one-shot-v1"
    assert owner.kimi_provider_args() == ["acp"]
    assert "kimi-sealed-bundle-text-v1" not in source
    assert "_kimi_bundle_file_binding" not in source


def test_kimi_transport_adds_no_second_lifecycle_or_smoke_path() -> None:
    text = OWNER_PATH.read_text(encoding="utf-8")
    forbidden = (
        "KIMI_PROMPTS_DIR",
        "KIMI_TASK_PROMPT",
        "KIMI_SMOKE_PROMPT",
        "kimi_agent_path",
        "initialize_kimi_agent",
        "resolve_kimi_executable",
        "build_kimi_launch_plan",
        "run_kimi_containment_smoke",
        "subprocess.run",
    )
    assert all(token not in text for token in forbidden)


def test_policy_bound_kimi_engineering_requires_external_worker_provenance() -> None:
    owner = _load_owner()
    control, decision = owner._policy_bound_external_control(
        "kimi",
        owner.Control(task_class="engineering", role="backend-engineer"),
    )

    assert decision["mutationClass"] == "bounded-write"
    assert control.ledger_role == "backend-engineer"
    assert control.ledger_role_explicit is True
    assert control.provider_flags == []
    assert owner.external_role_provenance(control, "kimi") == owner.ExternalRoleProvenance(
        assigned_role="backend-engineer",
        execution_role="external-worker",
    )
    for role in ("knowledge-archivist", "qa-engineer", "external-worker"):
        with pytest.raises(ValueError, match="^E_EXTERNAL_DISPATCH_POLICY_DENIED$"):
            owner._policy_bound_external_control(
                "kimi", owner.Control(task_class="engineering", role=role)
            )

    review, review_decision = owner._policy_bound_external_control(
        "kimi", owner.Control(task_class="review", role="qa-engineer")
    )
    assert review_decision["mutationClass"] == "read-only"
    assert owner.external_role_provenance(review, "kimi").execution_role == "external-reviewer"


class _FakeKimiAcpPeer:
    def __init__(
        self,
        *,
        out_of_order_update: bool = False,
        reverse_rpc: bool = False,
        eof_method: str | None = None,
        wrong_id_method: str | None = None,
        cancel_exception: Exception | None = None,
        boolean_initialize_id: bool = False,
        boolean_protocol_version: bool = False,
        model_config_result: dict[str, object] | None = None,
        thinking_config_result: dict[str, object] | None = None,
        interleaved_method: str | None = None,
        interleaved_update: dict[str, object] | None = None,
        permission_request: dict[str, object] | None = None,
        permission_request_id: object = "permission-rpc-1",
        tool_updates: tuple[dict[str, object], ...] = (),
    ) -> None:
        self.requests: list[dict[str, object]] = []
        self.client_responses: list[dict[str, object]] = []
        self.responses: list[bytes] = []
        self.out_of_order_update = out_of_order_update
        self.reverse_rpc = reverse_rpc
        self.eof_method = eof_method
        self.wrong_id_method = wrong_id_method
        self.cancel_exception = cancel_exception
        self.boolean_initialize_id = boolean_initialize_id
        self.boolean_protocol_version = boolean_protocol_version
        self.model_config_result = (
            {
                "configOptions": [
                    {
                        "type": "select",
                        "id": "model",
                        "name": "Model",
                        "category": "model",
                        "currentValue": "kimi-code/k3",
                        "options": [
                            {"value": "kimi-code/k3", "name": "K3"},
                        ],
                    },
                    {
                        "type": "select",
                        "id": "mode",
                        "name": "Mode",
                        "category": "mode",
                        "currentValue": "default",
                        "options": [
                            {"value": "default", "name": "Default"},
                        ],
                    },
                ]
            }
            if model_config_result is None
            else model_config_result
        )
        self.thinking_config_result = (
            {
                "configOptions": [
                    {
                        "type": "select",
                        "id": "thinking",
                        "name": "Thinking",
                        "category": "thinking",
                        "currentValue": "high",
                        "options": [
                            {"value": "low", "name": "Low"},
                            {"value": "high", "name": "High"},
                            {"value": "max", "name": "Max"},
                        ],
                    }
                ]
            }
            if thinking_config_result is None
            else thinking_config_result
        )
        self.interleaved_method = interleaved_method
        self.interleaved_update = interleaved_update
        self.permission_request = permission_request
        self.permission_request_id = permission_request_id
        self.tool_updates = tool_updates
        self.cancel_pending = False

    def write_line(
        self, payload: bytes, *, reserve_cleanup_fraction: float = 0.0
    ) -> int:
        request = json.loads(payload.decode("utf-8"))
        if "method" not in request:
            self.client_responses.append(request)
            return len(payload)
        self.requests.append(request)
        request_id = request.get("id")
        method = request.get("method")
        if method == "session/cancel":
            return len(payload)
        if method == self.eof_method:
            return len(payload)
        if self.out_of_order_update and method == "initialize":
            self.responses.append(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "session/update",
                        "params": {"sessionId": None, "update": {}},
                    },
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
        if self.reverse_rpc and method == "initialize":
            self.responses.append(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 99,
                        "method": "fs/read_text_file",
                        "params": {"path": "forbidden"},
                    },
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
        if method == self.interleaved_method and self.interleaved_update is not None:
            self.responses.append(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "session/update",
                        "params": {
                            "sessionId": "fake-session-1",
                            "update": self.interleaved_update,
                        },
                    },
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
        if method == "initialize":
            result = {
                "protocolVersion": (
                    True if self.boolean_protocol_version else 1
                ),
                "agentCapabilities": {},
            }
        elif method == "session/new":
            result = {"sessionId": "fake-session-1", "configOptions": [], "modes": {}}
        elif method == "session/set_config_option":
            result = (
                self.model_config_result
                if request["params"].get("configId") == "model"
                else self.thinking_config_result
            )
        elif method == "session/prompt":
            if self.cancel_exception is not None:
                self.cancel_pending = True
                return len(payload)
            for update in self.tool_updates:
                self.responses.append(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "session/update",
                            "params": {
                                "sessionId": "fake-session-1",
                                "update": update,
                            },
                        },
                        separators=(",", ":"),
                    ).encode("utf-8")
                    + b"\n"
                )
            if self.permission_request is not None:
                self.responses.append(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": self.permission_request_id,
                            "method": "session/request_permission",
                            "params": self.permission_request,
                        },
                        separators=(",", ":"),
                    ).encode("utf-8")
                    + b"\n"
                )
            self.responses.append(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "session/update",
                        "params": {
                            "sessionId": "fake-session-1",
                            "update": {
                                "sessionUpdate": "agent_message_chunk",
                                "content": {"type": "text", "text": "artifact\nGATE: PASS\n"},
                            },
                        },
                    },
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            result = {"stopReason": "end_turn"}
        elif method in {"session/close", "session/delete"}:
            result = {}
        else:
            raise AssertionError(f"unexpected request: {request}")
        self.responses.append(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": (
                        True
                        if method == "initialize" and self.boolean_initialize_id
                        else request_id + 100
                        if method == self.wrong_id_method and isinstance(request_id, int)
                        else request_id
                    ),
                    "result": result,
                },
                separators=(",", ":"),
            ).encode("utf-8")
            + b"\n"
        )
        return len(payload)

    def read_line(self, *, reserve_cleanup_fraction: float = 0.0) -> bytes:
        if self.cancel_pending and self.cancel_exception is not None:
            self.cancel_pending = False
            raise self.cancel_exception
        if not self.responses:
            raise EOFError("fake ACP peer has no queued response")
        return self.responses.pop(0)

    def cancellation_requested(self) -> bool:
        return False


def test_kimi_acp_one_shot_preserves_literal_task_bytes() -> None:
    owner = _load_owner()
    body = (
        "set(ROOT ${CMAKE_SOURCE_DIR})\r\n"
        "echo ${x} $USER $$ $$$$\n"
        "embedded:\x00; unicode: Привет 🌍"
    ).encode("utf-8")
    peer = _FakeKimiAcpPeer()
    exchange = owner.KimiAcpOneShotV1(body, "C:/private/run")

    exchange(peer)

    assert [request["method"] for request in peer.requests] == [
        "initialize",
        "session/new",
        "session/set_config_option",
        "session/set_config_option",
        "session/prompt",
        "session/close",
        "session/delete",
    ]
    assert peer.requests[0]["params"]["clientCapabilities"] == {}
    assert peer.requests[1]["params"]["mcpServers"] == []
    assert peer.requests[1]["params"]["additionalDirectories"] == []
    assert peer.requests[2]["params"] == {
        "sessionId": "fake-session-1",
        "configId": "model",
        "value": "kimi-code/k3",
    }
    assert peer.requests[3]["params"] == {
        "sessionId": "fake-session-1",
        "configId": "thinking",
        "value": "high",
    }
    prompt = peer.requests[4]["params"]["prompt"]
    assert prompt == [{"type": "text", "text": body.decode("utf-8")}]
    assert exchange.result_bytes == b"artifact\nGATE: PASS\n"


def test_kimi_acp_result_chunks_stay_under_memory_budget() -> None:
    owner = _load_owner()
    count = 200_000
    session_id = "profile-session"
    update = json.dumps(
        {
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": session_id,
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": "x"},
                },
            },
        },
        separators=(",", ":"),
    ).encode("utf-8") + b"\n"
    terminal = b'{"jsonrpc":"2.0","id":1,"result":{"stopReason":"end_turn"}}\n'

    class LazyPeer:
        def __init__(self) -> None:
            self.sent = 0

        def read_line(self) -> bytes:
            if self.sent < count:
                self.sent += 1
                return update
            self.sent += 1
            return terminal

    exchange = owner.KimiAcpOneShotV1(
        b"safe task", str(ROOT), result_max_bytes=count
    )
    object.__setattr__(exchange, "session_id", session_id)
    gc.collect()
    tracemalloc.start(1)
    try:
        result = exchange._response(LazyPeer(), 1, collect=True)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert result == {"stopReason": "end_turn"}
    assert exchange.result_bytes == b"x" * count
    assert peak < 4 * 1024 * 1024


@pytest.mark.parametrize(
    "model_config_result",
    (
        {},
        {"configOptions": []},
        {
            "configOptions": [
                {"id": "model", "currentValue": "kimi-code/kimi-for-coding"}
            ]
        },
        {
            "configOptions": [
                {"id": "model", "currentValue": "kimi-code/k3"},
                {"id": "model", "currentValue": "kimi-code/k3"},
            ]
        },
    ),
)
def test_kimi_acp_one_shot_rejects_unattested_fixed_model(
    model_config_result: dict[str, object],
) -> None:
    owner = _load_owner()
    peer = _FakeKimiAcpPeer(model_config_result=model_config_result)
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    with pytest.raises(ValueError, match="^E_KIMI_ACP_PROTOCOL$"):
        exchange(peer)

    assert all(request["method"] != "session/prompt" for request in peer.requests)
    assert [request["method"] for request in peer.requests][-2:] == [
        "session/close",
        "session/delete",
    ]


def test_kimi_acp_rejects_unattested_thinking_before_prompt() -> None:
    owner = _load_owner()
    peer = _FakeKimiAcpPeer(thinking_config_result={"configOptions": []})
    exchange = owner.KimiAcpOneShotV1(
        b"safe task", "C:/private/run", effort="max"
    )

    with pytest.raises(ValueError, match="^E_KIMI_ACP_PROTOCOL$"):
        exchange(peer)

    assert [request["params"].get("configId") for request in peer.requests] == [
        None,
        None,
        "model",
        "thinking",
        None,
        None,
    ]
    assert all(request["method"] != "session/prompt" for request in peer.requests)


def test_kimi_acp_max_thinking_readback_precedes_prompt() -> None:
    owner = _load_owner()
    peer = _FakeKimiAcpPeer(
        thinking_config_result={
            "configOptions": [
                {"id": "thinking", "currentValue": "max"}
            ]
        }
    )
    exchange = owner.KimiAcpOneShotV1(
        b"safe task", "C:/private/run", effort="max"
    )

    exchange(peer)

    thinking = next(
        request for request in peer.requests
        if request["params"].get("configId") == "thinking"
    )
    assert thinking["params"] == {
        "sessionId": "fake-session-1",
        "configId": "thinking",
        "value": "max",
    }
    assert peer.requests.index(thinking) < next(
        index
        for index, request in enumerate(peer.requests)
        if request["method"] == "session/prompt"
    )


@pytest.mark.parametrize("effort", ("high", "max"))
def test_kimi_empty_launch_flags_accept_resolved_effort_and_legacy_unsupported(
    effort: str,
) -> None:
    owner = _load_owner()
    provenance = owner.ExecutionProvenance(
        "fixture-item",
        "backend-engineer",
        "kimi",
        "kimi-code/k3",
        effort,
        (),
        "fixture-artifact",
        "dispatch-fixture",
        "evidence-fixture",
        "configured-per-run",
    )
    assert provenance.effort == effort
    outcome = owner.FinalOutcome(
        0, "COMPLETE:EXTERNAL_NONAUTHORIZING", "passed", "PASS", "fixture",
        0, "COMPLETE:PASS", "passed", "PASS", "fixture", "complete", 0, "", False, 0,
    )
    payload = owner.parse_provider_result(
        owner.build_provider_result_line(
            "kimi", "kimi-code/k3", effort, "GATE: PASS\n", outcome,
            cancelled=False, timed_out=False,
            role_provenance=owner.ExternalRoleProvenance("none", "none"),
            provenance=provenance,
        )
    )
    assert payload["launchFlags"] == []
    assert payload["effort"] == effort


def test_kimi_acp_postcreation_error_preserves_primary_and_attempts_delete_after_close_error() -> None:
    owner = _load_owner()
    peer = _FakeKimiAcpPeer(
        model_config_result={},
        wrong_id_method="session/close",
    )
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    with pytest.raises(ValueError) as caught:
        exchange(peer)

    assert str(caught.value) == "E_KIMI_ACP_PROTOCOL"
    assert [request["method"] for request in peer.requests][-2:] == [
        "session/close",
        "session/delete",
    ]
    assert isinstance(caught.value.__cause__, ValueError)


def test_kimi_acp_close_deadline_reserves_delete_and_preserves_first_error() -> None:
    owner = _load_owner()

    class CloseDeadlinePeer:
        def __init__(self) -> None:
            self.methods: list[str] = []
            self.write_fractions: list[float] = []
            self.read_fractions: list[float] = []

        def begin_cleanup(self) -> None:
            return None

        def write_line(
            self, payload: bytes, *, reserve_cleanup_fraction: float = 0.0
        ) -> int:
            self.methods.append(json.loads(payload.decode("utf-8"))["method"])
            self.write_fractions.append(reserve_cleanup_fraction)
            return len(payload)

        def read_line(self, *, reserve_cleanup_fraction: float = 0.0) -> bytes:
            self.read_fractions.append(reserve_cleanup_fraction)
            if self.methods[-1] == "session/close":
                raise owner.ProcessSupervisionError("PSV1-DEADLINE", "deadline")
            return b'{"jsonrpc":"2.0","id":2,"result":{}}\n'

    peer = CloseDeadlinePeer()
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")
    exchange.session_id = "synthetic-session"

    with pytest.raises(owner.ProcessSupervisionError) as caught:
        exchange._cleanup_session(peer, cancel=False)

    assert caught.value.failure_id == "PSV1-DEADLINE"
    assert peer.methods == ["session/close", "session/delete"]
    assert peer.write_fractions == [0.5, 0.0]
    assert peer.read_fractions == [0.5, 0.0]


def test_kimi_acp_close_deadline_remains_first_error_when_delete_write_fails() -> None:
    owner = _load_owner()

    class DeleteFailurePeer:
        def __init__(self) -> None:
            self.methods: list[str] = []

        def begin_cleanup(self) -> None:
            return None

        def write_line(
            self, payload: bytes, *, reserve_cleanup_fraction: float = 0.0
        ) -> int:
            method = json.loads(payload.decode("utf-8"))["method"]
            self.methods.append(method)
            if method == "session/delete":
                raise owner.ProcessSupervisionError(
                    "PSV1-KIMI-ACP-PROTOCOL", "stdin-delivery"
                )
            return len(payload)

        def read_line(self, *, reserve_cleanup_fraction: float = 0.0) -> bytes:
            raise owner.ProcessSupervisionError("PSV1-DEADLINE", "deadline")

    peer = DeleteFailurePeer()
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")
    exchange.session_id = "synthetic-session"

    with pytest.raises(owner.ProcessSupervisionError) as caught:
        exchange._cleanup_session(peer, cancel=False)

    assert caught.value.failure_id == "PSV1-DEADLINE"
    assert peer.methods == ["session/close", "session/delete"]


@pytest.mark.parametrize(
    "control_update",
    (
        {"sessionUpdate": "available_commands_update", "availableCommands": []},
        {"sessionUpdate": "current_mode_update", "currentModeId": "default"},
        {"sessionUpdate": "config_option_update", "configOptions": []},
        {"sessionUpdate": "usage_update", "used": 1, "size": 1048576},
        {"sessionUpdate": "session_info_update", "title": None},
    ),
)
def test_kimi_acp_demultiplexes_control_updates_while_awaiting_model_response(
    control_update: dict[str, object],
) -> None:
    owner = _load_owner()
    peer = _FakeKimiAcpPeer(
        interleaved_method="session/set_config_option",
        interleaved_update=control_update,
    )
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    exchange(peer)

    assert exchange.result_bytes == b"artifact\nGATE: PASS\n"
    assert any(request["method"] == "session/prompt" for request in peer.requests)


@pytest.mark.parametrize("cleanup_method", ("session/close", "session/delete"))
def test_kimi_acp_demultiplexes_control_updates_while_awaiting_cleanup_response(
    cleanup_method: str,
) -> None:
    owner = _load_owner()
    peer = _FakeKimiAcpPeer(
        interleaved_method=cleanup_method,
        interleaved_update={
            "sessionUpdate": "config_option_update",
            "configOptions": [],
        },
    )
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    exchange(peer)

    assert [request["method"] for request in peer.requests][-2:] == [
        "session/close",
        "session/delete",
    ]


def test_kimi_acp_rejects_prompt_output_update_between_rpc_replies() -> None:
    owner = _load_owner()
    peer = _FakeKimiAcpPeer(
        interleaved_method="session/set_config_option",
        interleaved_update={
            "sessionUpdate": "agent_message_chunk",
            "content": {"type": "text", "text": "out-of-phase"},
        },
    )
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    with pytest.raises(ValueError, match="^E_KIMI_ACP_PROTOCOL$"):
        exchange(peer)

    assert all(request["method"] != "session/prompt" for request in peer.requests)


def _permission_request(options: list[dict[str, str]]) -> dict[str, object]:
    return {
        "sessionId": "fake-session-1",
        "options": options,
        "toolCall": {
            "toolCallId": "1:tool-call-1",
            "title": "Read",
            "kind": "read",
            "status": "in_progress",
            "content": [
                {
                    "type": "content",
                    "content": {"type": "text", "text": "private tool content"},
                }
            ],
        },
    }


@pytest.mark.parametrize(
    ("configured", "kind", "option_id"),
    (
        ("reject", "reject_once", "deny-this-request"),
        ("approve_once", "allow_once", "permit-once-custom"),
        ("approve_always", "allow_always", "permit-session-custom"),
    ),
)
def test_kimi_acp_permission_uses_exact_offered_option_and_rpc_id(
    configured: str, kind: str, option_id: str
) -> None:
    owner = _load_owner()
    peer = _FakeKimiAcpPeer(
        permission_request=_permission_request(
            [
                {"optionId": "other", "name": "Other", "kind": "reject_once"},
                {"optionId": option_id, "name": "Selected", "kind": kind},
            ]
            if kind != "reject_once"
            else [
                {"optionId": "permit", "name": "Permit", "kind": "allow_once"},
                {"optionId": option_id, "name": "Reject", "kind": kind},
            ]
        ),
        permission_request_id="server-rpc-42",
    )
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")
    exchange.permission = configured

    exchange(peer)

    assert peer.client_responses == [
        {
            "jsonrpc": "2.0",
            "id": "server-rpc-42",
            "result": {
                "outcome": {"outcome": "selected", "optionId": option_id}
            },
        }
    ]
    observed = getattr(exchange, "observed_receipt", lambda: None)()
    assert observed == {
        "toolCalls": [],
        "permissionDecisions": [
            {"id": "1:tool-call-1", "title": "Read", "decision": configured}
        ],
    }


@pytest.mark.parametrize(
    ("request_id", "options"),
    (
        (
            True,
            [{"optionId": "deny", "name": "Reject", "kind": "reject_once"}],
        ),
        (
            17,
            [{"optionId": "permit", "name": "Permit", "kind": "allow_once"}],
        ),
        (
            18,
            [
                {"optionId": "deny-a", "name": "Reject A", "kind": "reject_once"},
                {"optionId": "deny-b", "name": "Reject B", "kind": "reject_once"},
            ],
        ),
    ),
)
def test_kimi_acp_permission_rejects_bad_id_or_option_mismatch(
    request_id: object, options: list[dict[str, str]]
) -> None:
    owner = _load_owner()
    peer = _FakeKimiAcpPeer(
        permission_request=_permission_request(options),
        permission_request_id=request_id,
    )
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")
    exchange.permission = "reject"

    with pytest.raises(ValueError, match="^E_KIMI_ACP_PROTOCOL$"):
        exchange(peer)

    assert peer.client_responses == []


def test_kimi_acp_merges_tool_updates_without_content_or_raw_output() -> None:
    owner = _load_owner()
    peer = _FakeKimiAcpPeer(
        tool_updates=(
            {
                "sessionUpdate": "tool_call",
                "toolCallId": "1:tool-call-1",
                "title": "Read",
                "status": "in_progress",
                "content": [
                    {
                        "type": "content",
                        "content": {"type": "text", "text": "secret-value"},
                    }
                ],
                "rawInput": {"path": "C:/Users/<user>/private.txt"},
            },
            {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "1:tool-call-1",
                "title": "Read",
            },
            {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "1:tool-call-1",
                "status": "completed",
                "rawOutput": "secret-value",
            },
        )
    )
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    exchange(peer)

    observed_method = getattr(exchange, "observed_receipt", None)
    assert callable(observed_method)
    observed = observed_method()
    assert observed == {
        "toolCalls": [
            {"id": "1:tool-call-1", "title": "Read", "status": "completed"}
        ],
        "permissionDecisions": [],
    }
    assert "secret-value" not in json.dumps(observed)
    assert "private.txt" not in json.dumps(observed)


def test_kimi_observed_titles_redact_selected_cwd_and_mcp_secret(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    server = owner.KimiMcpServerV1(
        name="private-mcp",
        command="fixture",
        args=(),
        env=(owner.KimiNameValueV1("TOKEN", "secret-value"),),
    )
    permission = _permission_request(
        [{"optionId": "deny-custom", "name": "Reject", "kind": "reject_once"}]
    )
    permission["toolCall"]["title"] = f"Read {tmp_path}"
    peer = _FakeKimiAcpPeer(
        tool_updates=(
            {
                "sessionUpdate": "tool_call",
                "toolCallId": "1:tool-call-1",
                "title": "Read secret-value",
                "status": "in_progress",
            },
        ),
        permission_request=permission,
    )
    exchange = owner.KimiAcpOneShotV1(
        b"safe task", str(tmp_path), (server,), "reject"
    )

    exchange(peer)

    observed = exchange.observed_receipt()
    assert observed["toolCalls"][0]["title"] == "<redacted>"
    assert observed["permissionDecisions"][0]["title"] == "<redacted>"
    visible = json.dumps(observed)
    assert "secret-value" not in visible
    assert str(tmp_path) not in visible


def test_kimi_path_bearing_optional_titles_do_not_erase_safe_answer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()
    machine_title = (
        "Bash C:" + "\\Users\\private-machine\\Python314\\python.exe"
        " -B check_worker.py"
    )
    permission = _permission_request(
        [{"optionId": "allow-custom", "name": "Allow", "kind": "allow_once"}]
    )
    permission["toolCall"]["title"] = machine_title
    peer = _FakeKimiAcpPeer(
        tool_updates=(
            {
                "sessionUpdate": "tool_call",
                "toolCallId": "1:tool-call-1",
                "title": machine_title,
                "status": "in_progress",
            },
        ),
        permission_request=permission,
    )
    capabilities = owner.KimiCapabilitySelectionV1(
        tools=("Read", "Bash"),
        permission="approve_once",
        cwd=str(tmp_path),
    )
    exchange = owner.KimiAcpOneShotV1(
        b"safe task", str(tmp_path), (), "approve_once"
    )

    exchange(peer)
    observed = exchange.observed_receipt()
    code, payload, _notes, lifecycle = _finalize_kimi(
        owner,
        tmp_path,
        monkeypatch,
        capsys,
        stdout=exchange.result_bytes,
        stderr=b"",
        capabilities=capabilities,
        observed=observed,
    )

    assert code == 0
    assert payload["resultText"] == "artifact\nGATE: PASS\n"
    assert payload["token"] == "COMPLETE:EXTERNAL_NONAUTHORIZING"
    assert payload["observed"] == {
        "toolCalls": [
            {
                "id": "1:tool-call-1",
                "title": "<redacted>",
                "status": "in_progress",
            }
        ],
        "permissionDecisions": [
            {
                "id": "1:tool-call-1",
                "title": "<redacted>",
                "decision": "approve_once",
            }
        ],
    }
    assert machine_title not in json.dumps(payload)
    assert not lifecycle.run_dir.exists()


def test_kimi_optional_title_redacts_when_machine_path_classifier_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _load_owner()
    finder = getattr(owner, "_machine_path_finder", None)
    assert callable(finder)
    monkeypatch.setattr(owner, "_machine_path_finder", lambda: None)
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    assert exchange._receipt_text("Bash synthetic worker check") == "<redacted>"


@pytest.mark.parametrize(
    "update",
    (
        {
            "sessionUpdate": "tool_call_update",
            "toolCallId": "unknown",
            "status": "completed",
        },
        {
            "sessionUpdate": "tool_call",
            "toolCallId": "1:tool-call-1",
            "title": "Read",
            "status": "unknown-status",
        },
    ),
)
def test_kimi_acp_rejects_unmergeable_tool_evidence(
    update: dict[str, object],
) -> None:
    owner = _load_owner()
    peer = _FakeKimiAcpPeer(tool_updates=(update,))
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    with pytest.raises(ValueError, match="^E_KIMI_ACP_PROTOCOL$"):
        exchange(peer)


def test_kimi_acp_one_shot_refuses_reverse_rpc() -> None:
    owner = _load_owner()
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    with pytest.raises(ValueError, match="^E_KIMI_ACP_PROTOCOL$"):
        exchange(_FakeKimiAcpPeer(reverse_rpc=True))


def test_kimi_acp_one_shot_rejects_session_update_before_prompt() -> None:
    owner = _load_owner()
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    with pytest.raises(ValueError, match="^E_KIMI_ACP_PROTOCOL$"):
        exchange(_FakeKimiAcpPeer(out_of_order_update=True))


def test_kimi_acp_one_shot_rejects_boolean_response_id() -> None:
    owner = _load_owner()
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    with pytest.raises(ValueError, match="^E_KIMI_ACP_PROTOCOL$"):
        exchange(_FakeKimiAcpPeer(boolean_initialize_id=True))


def test_kimi_acp_one_shot_rejects_boolean_protocol_version() -> None:
    owner = _load_owner()
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    with pytest.raises(ValueError, match="^E_KIMI_ACP_PROTOCOL$"):
        exchange(_FakeKimiAcpPeer(boolean_protocol_version=True))


@pytest.mark.parametrize(
    "peer",
    (
        _FakeKimiAcpPeer(eof_method="session/new"),
        _FakeKimiAcpPeer(wrong_id_method="initialize"),
    ),
)
def test_kimi_acp_one_shot_rejects_eof_and_wrong_response_id(peer) -> None:
    owner = _load_owner()
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    with pytest.raises(ValueError, match="^E_KIMI_ACP_PROTOCOL$"):
        exchange(peer)


def test_kimi_acp_cancel_closes_and_deletes_session() -> None:
    owner = _load_owner()
    cancelled = owner.ProcessSupervisionError("PSV1-CANCELLED", "cancellation")
    peer = _FakeKimiAcpPeer(cancel_exception=cancelled)
    exchange = owner.KimiAcpOneShotV1(b"safe task", "C:/private/run")

    with pytest.raises(owner.ProcessSupervisionError) as caught:
        exchange(peer)

    assert caught.value.failure_id == "PSV1-CANCELLED"
    assert [request["method"] for request in peer.requests][-3:] == [
        "session/cancel",
        "session/close",
        "session/delete",
    ]


def test_kimi_private_home_aliases_unlink_before_lifecycle_removes_private_state(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    user_data = tmp_path / "user-data"
    credentials = user_data / "credentials"
    credentials.mkdir(parents=True)
    config = user_data / "config.toml"
    secret = credentials / "token"
    config.write_text("default_model='kimi-code/k3'\n", encoding="utf-8")
    original_config = config.read_bytes()
    secret.write_text("private\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    try:
        aliases = owner.KimiPrivateHomeAliasesV1.create(run_dir, user_data)
    except OSError as exc:
        pytest.skip(f"file/directory symlinks unavailable: {exc}")

    private_config = aliases.home / "config.toml"
    assert private_config.is_file()
    assert not private_config.is_symlink()
    assert private_config.read_bytes() == (
        original_config
        + b"\n"
        b"[tools]\n"
        b'enabled = ["Agent"]\n'
        b'disabled = ["Agent","AgentSwarm"]\n'
    )
    assert (aliases.home / "credentials").is_symlink()
    private_session = aliases.home / "sessions" / "session.json"
    private_session.parent.mkdir()
    private_session.write_text("{}\n", encoding="utf-8")
    aliases.cleanup()

    assert aliases.home.is_dir()
    assert not os.path.lexists(private_config)
    assert not os.path.lexists(aliases.home / "credentials")
    assert private_session.read_text(encoding="utf-8") == "{}\n"
    assert config.read_bytes() == original_config
    assert secret.read_text(encoding="utf-8") == "private\n"


def test_kimi_private_run_materializes_fixed_zero_capability_agent_profile(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    (user_data / "config.toml").write_text(
        "default_model='kimi-code/k3'\n", encoding="utf-8"
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    try:
        owner.KimiPrivateHomeAliasesV1.create(run_dir, user_data)
    except OSError as exc:
        pytest.skip(f"file symlinks unavailable: {exc}")

    profile = run_dir / ".kimi-code" / "agents" / "agent.md"
    assert profile.read_bytes() == (
        b"---\n"
        b"name: agent\n"
        b"description: Orchestrarium finite ACP result agent\n"
        b"override: true\n"
        b"tools: []\n"
        b"subagents: []\n"
        b"---\n\n"
        b"${base_prompt}\n"
    )


def _write_kimi_capabilities(
    path: Path,
    *,
    cwd: Path | None = None,
    tools: list[str] | None = None,
    mcp_servers: list[dict[str, object]] | None = None,
    subagents: list[str] | None = None,
    permission: str = "reject",
) -> None:
    path.write_text(
        json.dumps(
            {
                "v": 1,
                "tools": [] if tools is None else tools,
                "mcpServers": [] if mcp_servers is None else mcp_servers,
                "subagents": [] if subagents is None else subagents,
                "permission": permission,
                "cwd": None if cwd is None else str(cwd),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_kimi_capabilities_file_parses_exact_shape_without_provider_flags(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    capabilities = tmp_path / "capabilities.json"
    _write_kimi_capabilities(capabilities)

    control = owner.parse_control(
        [
            "fixture",
            "--kimi-capabilities-file",
            str(capabilities),
            "--task-class",
            "review",
            "--role",
            "qa-engineer",
        ],
        external=True,
    )

    assert control.provider_flags == []
    selected = getattr(control, "kimi_capabilities", None)
    assert selected is not None
    assert selected.tools == ()
    assert selected.mcp_servers == ()
    assert selected.subagents == ()
    assert selected.permission == "reject"
    assert selected.cwd is None


def test_kimi_help_advertises_optional_capabilities_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()

    assert owner.kimi_main(["--help"]) == 0

    assert "[--kimi-capabilities-file <json>]" in capsys.readouterr().out


@pytest.mark.parametrize(
    "raw",
    (
        b'{"v":1,"v":1,"tools":[],"mcpServers":[],"subagents":[],"permission":"reject","cwd":null}',
        b'{"v":1,"tools":[],"mcpServers":[],"subagents":[],"permission":"reject","cwd":null,"extra":true}',
        b'{"v":2,"tools":[],"mcpServers":[],"subagents":[],"permission":"reject","cwd":null}',
        b'{"v":true,"tools":[],"mcpServers":[],"subagents":[],"permission":"reject","cwd":null}',
        b'{"v":1,"tools":"Read","mcpServers":[],"subagents":[],"permission":"reject","cwd":null}',
        b'{"v":1,"tools":["Read","Read"],"mcpServers":[],"subagents":[],"permission":"reject","cwd":null}',
        b'{"v":1,"tools":[],"mcpServers":[],"subagents":[],"permission":"sometimes","cwd":null}',
        b'{"v":1,"tools":[],"mcpServers":[{"name":"local","command":"tool","type":"stdio"}],"subagents":[],"permission":"reject","cwd":null}',
        b'{"v":1,"tools":[],"mcpServers":[{"name":"local","command":"tool"}],"subagents":[],"permission":"reject","cwd":null}',
        b'{"v":1,"tools":[],"mcpServers":[{"name":"remote","type":"http","url":"https://example.invalid"}],"subagents":[],"permission":"reject","cwd":null}',
        b'{"v":1,"tools":[],"mcpServers":[{"name":"remote","type":"sse","url":"https://example.invalid"}],"subagents":[],"permission":"reject","cwd":null}',
        b'{"v":1,"tools":[],"mcpServers":[{"name":"remote","type":"http","url":"https://example.invalid","args":[]}],"subagents":[],"permission":"reject","cwd":null}',
        b'{"v":1,"tools":[],"mcpServers":[{"name":"dup","command":"one"},{"name":"dup","command":"two"}],"subagents":[],"permission":"reject","cwd":null}',
        b'{"v":1,"tools":[],"mcpServers":[{"name":"local","command":"tool","env":[{"name":"TOKEN","value":"one"},{"name":"TOKEN","value":"two"}]}],"subagents":[],"permission":"reject","cwd":null}',
    ),
)
def test_kimi_capabilities_file_rejects_invalid_shapes(
    tmp_path: Path, raw: bytes
) -> None:
    owner = _load_owner()
    capabilities = tmp_path / "invalid.json"
    capabilities.write_bytes(raw)
    load = getattr(owner, "read_kimi_capability_selection", lambda _path: None)

    with pytest.raises(ValueError, match="^E_KIMI_CAPABILITIES_INVALID$"):
        load(capabilities)


def test_kimi_capabilities_file_rejects_oversize_and_invalid_cwd_without_echo(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    load = getattr(owner, "read_kimi_capability_selection", lambda _path: None)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * (owner.PROMPT_SNAPSHOT_MAX_BYTES + 1))
    invalid_cwd = tmp_path / "invalid-cwd.json"
    _write_kimi_capabilities(invalid_cwd)
    document = json.loads(invalid_cwd.read_text(encoding="utf-8"))
    document["cwd"] = "relative/private-workdir"
    invalid_cwd.write_text(json.dumps(document), encoding="utf-8")
    missing_cwd = tmp_path / "missing-cwd.json"
    _write_kimi_capabilities(missing_cwd)
    document = json.loads(missing_cwd.read_text(encoding="utf-8"))
    document["cwd"] = str(tmp_path / "does-not-exist")
    missing_cwd.write_text(json.dumps(document), encoding="utf-8")

    for path in (oversized, invalid_cwd, missing_cwd):
        with pytest.raises(ValueError) as caught:
            load(path)
        assert str(caught.value) == "E_KIMI_CAPABILITIES_INVALID"
        assert str(path) not in str(caught.value)
        assert "private-workdir" not in str(caught.value)


@pytest.mark.parametrize(
    ("tools", "subagents"),
    (
        (["Agent"], []),
        (["AgentSwarm"], []),
        ([], ["future-explorer"]),
        (["Agent"], ["future-explorer"]),
        ([], ["*"]),
        (["Agent"], ["*", "future-explorer"]),
    ),
)
def test_kimi_capabilities_file_rejects_children_explicitly(
    tmp_path: Path,
    tools: list[str],
    subagents: list[str],
) -> None:
    owner = _load_owner()
    capabilities = tmp_path / "capabilities.json"
    _write_kimi_capabilities(
        capabilities,
        tools=tools,
        subagents=subagents,
    )

    with pytest.raises(ValueError, match="^E_KIMI_CHILD_SELECTION_UNSUPPORTED$"):
        owner._prevalidate_policy_bound_external_launch(
            "kimi",
            [
                "fixture",
                "--kimi-capabilities-file",
                str(capabilities),
                "--task-class",
                "engineering",
                "--role",
                "backend-engineer",
            ],
        )


@pytest.mark.parametrize(
    ("tools", "expected_disabled"),
    (
        (["Agent"], ["AgentSwarm"]),
        (["AgentSwarm"], ["Agent"]),
        (["Read", "Agent", "AgentSwarm"], []),
    ),
)
def test_kimi_wildcard_child_permission_projects_only_selected_dispatch_tools(
    tmp_path: Path,
    tools: list[str],
    expected_disabled: list[str],
) -> None:
    owner = _load_owner()
    capabilities = tmp_path / "capabilities.json"
    _write_kimi_capabilities(capabilities, tools=tools, subagents=["*"])

    selection = owner.read_kimi_capability_selection(capabilities)
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    aliases = owner.KimiPrivateHomeAliasesV1.create(
        run_dir, user_data, selection
    )
    parsed = tomllib.loads(
        (aliases.home / "config.toml").read_text(encoding="utf-8")
    )

    assert selection.subagents == ("*",)
    assert parsed["tools"] == {
        "enabled": tools,
        "disabled": expected_disabled,
    }
    assert owner.kimi_selected_receipt(selection)["subagents"] == ["*"]
    assert "future-explorer" not in json.dumps(
        owner.kimi_selected_receipt(selection)
    )
    aliases.cleanup()


@pytest.mark.parametrize(
    ("selected_tools", "expected_enabled", "expected_active"),
    (
        ((), ["Agent"], {"Read": False, "Bash": False, "mcp__other__tool": False}),
        (
            ("Read", "mcp__selected__tool"),
            ["Read", "mcp__selected__tool"],
            {
                "Read": True,
                "Bash": False,
                "mcp__selected__tool": True,
                "mcp__other__tool": False,
            },
        ),
    ),
)
def test_kimi_private_config_projects_native_tool_upper_bound(
    tmp_path: Path,
    selected_tools: tuple[str, ...],
    expected_enabled: list[str],
    expected_active: dict[str, bool],
) -> None:
    owner = _load_owner()
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    aliases = owner.KimiPrivateHomeAliasesV1.create(
        run_dir,
        user_data,
        owner.KimiCapabilitySelectionV1(tools=selected_tools),
    )

    private_config = aliases.home / "config.toml"
    parsed = tomllib.loads(private_config.read_text(encoding="utf-8"))
    assert parsed == {
        "tools": {
            "enabled": expected_enabled,
            "disabled": ["Agent", "AgentSwarm"],
        }
    }

    def active(name: str) -> bool:
        enabled = parsed["tools"]["enabled"]
        disabled = parsed["tools"]["disabled"]
        allowed = name in enabled
        return allowed and name not in disabled

    assert {name: active(name) for name in expected_active} == expected_active
    aliases.cleanup()
    assert not private_config.exists()


def test_kimi_private_config_preserves_exact_matching_user_bytes(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    original = (
        b"default_model = 'kimi-code/k3'\n"
        b"[tools]\n"
        b'enabled = ["Read", "mcp__selected__tool"]\n'
        b'disabled = ["Agent", "AgentSwarm"]\n'
    )
    user_config = user_data / "config.toml"
    user_config.write_bytes(original)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    aliases = owner.KimiPrivateHomeAliasesV1.create(
        run_dir,
        user_data,
        owner.KimiCapabilitySelectionV1(
            tools=("Read", "mcp__selected__tool")
        ),
    )

    private_config = aliases.home / "config.toml"
    assert not private_config.is_symlink()
    assert private_config.read_bytes() == original
    assert user_config.read_bytes() == original
    aliases.cleanup()
    assert user_config.read_bytes() == original


@pytest.mark.parametrize(
    ("selected_tools", "original"),
    (
        (
            ("Read", "Bash"),
            b'[tools]\nenabled = ["Bash", "Read", "Read"]\n'
            b'disabled = ["AgentSwarm", "Agent", "Bash", "Agent"]\n',
        ),
        (
            ("Read", "Bash", "mcp__selected__tool"),
            b'[tools]\nenabled = ["Read"]\n'
            b'disabled = ["Agent", "AgentSwarm"]\n',
        ),
    ),
)
def test_kimi_private_config_preserves_semantically_narrower_user_policy_bytes(
    tmp_path: Path,
    selected_tools: tuple[str, ...],
    original: bytes,
) -> None:
    owner = _load_owner()
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    user_config = user_data / "config.toml"
    user_config.write_bytes(original)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    aliases = owner.KimiPrivateHomeAliasesV1.create(
        run_dir,
        user_data,
        owner.KimiCapabilitySelectionV1(tools=selected_tools),
    )

    assert (aliases.home / "config.toml").read_bytes() == original
    assert user_config.read_bytes() == original
    aliases.cleanup()
    assert user_config.read_bytes() == original


@pytest.mark.skipif(os.name != "nt", reason="Windows file-symlink contract")
def test_kimi_private_config_accepts_file_symlink_without_mutating_target(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    target = tmp_path / "physical" / "config.toml"
    target.parent.mkdir()
    original = b"default_model = 'kimi-code/k3'\n"
    target.write_bytes(original)
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    link = user_data / "config.toml"
    link.symlink_to(target)
    link_target = os.readlink(link)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    aliases = owner.KimiPrivateHomeAliasesV1.create(run_dir, user_data)

    assert (aliases.home / "config.toml").read_bytes() == (
        original
        + b"\n"
        b"[tools]\n"
        b'enabled = ["Agent"]\n'
        b'disabled = ["Agent","AgentSwarm"]\n'
    )
    assert link.is_symlink()
    assert os.readlink(link) == link_target
    assert target.read_bytes() == original
    aliases.cleanup()
    assert link.is_symlink()
    assert target.read_bytes() == original


@pytest.mark.skipif(os.name != "nt", reason="Windows directory-link contract")
@pytest.mark.parametrize("link_kind", ("symlink", "junction"))
def test_kimi_private_config_accepts_linked_user_directory_without_mutation(
    tmp_path: Path,
    link_kind: str,
) -> None:
    owner = _load_owner()
    physical = tmp_path / "physical-user-data"
    physical.mkdir()
    original = b"default_model = 'kimi-code/k3'\n"
    target = physical / "config.toml"
    target.write_bytes(original)
    user_data = tmp_path / "linked-user-data"
    if link_kind == "symlink":
        user_data.symlink_to(physical, target_is_directory=True)
    else:
        result = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(user_data), str(physical)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode != 0:
            pytest.skip(f"junction unavailable: {result.stderr.strip()}")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    try:
        aliases = owner.KimiPrivateHomeAliasesV1.create(run_dir, user_data)

        assert (aliases.home / "config.toml").read_bytes() == (
            original
            + b"\n"
            b"[tools]\n"
            b'enabled = ["Agent"]\n'
            b'disabled = ["Agent","AgentSwarm"]\n'
        )
        assert target.read_bytes() == original
        aliases.cleanup()
        assert target.read_bytes() == original
    finally:
        if os.path.lexists(user_data):
            if user_data.is_symlink():
                user_data.unlink()
            else:
                user_data.rmdir()


@pytest.mark.skipif(os.name != "nt", reason="Windows file-symlink contract")
def test_kimi_private_config_rejects_broken_file_symlink_visibly(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    link = user_data / "config.toml"
    link.symlink_to(tmp_path / "missing-config.toml")
    link_target = os.readlink(link)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with pytest.raises(
        ValueError, match="^E_KIMI_CAPABILITIES_CONFIG_CONFLICT$"
    ):
        owner.KimiPrivateHomeAliasesV1.create(run_dir, user_data)

    assert link.is_symlink()
    assert os.readlink(link) == link_target
    assert not (run_dir / "kimi-home").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows file-symlink contract")
def test_kimi_private_config_rejects_link_target_change_during_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _load_owner()
    first = tmp_path / "first.toml"
    second = tmp_path / "second.toml"
    first.write_bytes(b"default_model = 'kimi-code/k3'\n")
    second.write_bytes(b"default_model = 'kimi-code/k3'\n")
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    link = user_data / "config.toml"
    link.symlink_to(first)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    original_resolve = owner.Path.resolve
    candidate = owner.Path(os.path.abspath(link))
    resolutions = 0

    def retarget_on_second_resolve(path: Path, *args, **kwargs):
        nonlocal resolutions
        if owner.Path(os.path.abspath(path)) == candidate:
            resolutions += 1
            if resolutions == 2:
                link.unlink()
                link.symlink_to(second)
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(owner.Path, "resolve", retarget_on_second_resolve)

    with pytest.raises(
        ValueError, match="^E_KIMI_CAPABILITIES_CONFIG_CONFLICT$"
    ):
        owner.KimiPrivateHomeAliasesV1.create(run_dir, user_data)

    assert resolutions == 2
    assert first.read_bytes() == b"default_model = 'kimi-code/k3'\n"
    assert second.read_bytes() == b"default_model = 'kimi-code/k3'\n"
    assert not (run_dir / "kimi-home").exists()


@pytest.mark.parametrize(
    "original",
    (
        b'[tools]\nenabled = ["Bash"]\ndisabled = ["Agent","AgentSwarm"]\n',
        b'[tools]\nenabled = ["Read"]\ndisabled = ["Agent"]\n',
        b'[tools]\nenabled = []\ndisabled = ["Agent","AgentSwarm"]\n',
        b'[tools]\nenabled = ["Read"]\ndisabled = ["Agent","AgentSwarm"]\nextra = true\n',
        b'[tools]\nenabled = [" Read"]\ndisabled = ["Agent","AgentSwarm"]\n',
        b'[tools]\nenabled = ["mcp__selected__*"]\ndisabled = ["Agent","AgentSwarm"]\n',
        b"[tools\n",
    ),
)
def test_kimi_private_config_rejects_conflict_without_mutating_user_bytes(
    tmp_path: Path,
    original: bytes,
) -> None:
    owner = _load_owner()
    user_data = tmp_path / "user-data"
    user_data.mkdir()
    user_config = user_data / "config.toml"
    user_config.write_bytes(original)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with pytest.raises(
        ValueError, match="^E_KIMI_CAPABILITIES_CONFIG_CONFLICT$"
    ):
        owner.KimiPrivateHomeAliasesV1.create(
            run_dir,
            user_data,
            owner.KimiCapabilitySelectionV1(tools=("Read",)),
        )

    assert user_config.read_bytes() == original
    assert not (run_dir / "kimi-home").exists()


def test_kimi_private_config_is_removed_when_alias_setup_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _load_owner()
    user_data = tmp_path / "user-data"
    (user_data / "credentials").mkdir(parents=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def fail_symlink(*_args, **_kwargs) -> None:
        raise OSError("synthetic")

    monkeypatch.setattr(owner.os, "symlink", fail_symlink)

    with pytest.raises(OSError, match="synthetic"):
        owner.KimiPrivateHomeAliasesV1.create(run_dir, user_data)

    assert not (run_dir / "kimi-home" / "config.toml").exists()


def test_kimi_selected_cwd_and_mcp_variants_reach_session_new_unchanged(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    selected_cwd = tmp_path / "selected-cwd"
    selected_cwd.mkdir()
    capabilities = tmp_path / "capabilities.json"
    expected_mcp = [
        {
            "name": "local",
            "command": "fixture-tool",
            "args": ["--mode", "two words"],
            "env": [{"name": "FIXTURE_TOKEN", "value": "secret-value"}],
        },
        {
            "name": "remote-http",
            "type": "http",
            "url": "https://example.invalid/mcp",
            "headers": [{"name": "Authorization", "value": "private-header"}],
        },
        {
            "name": "remote-sse",
            "type": "sse",
            "url": "https://example.invalid/sse",
            "headers": [],
        },
    ]
    _write_kimi_capabilities(
        capabilities,
        cwd=selected_cwd,
        mcp_servers=expected_mcp,
    )
    load = getattr(owner, "read_kimi_capability_selection", lambda _path: None)
    selection = load(capabilities)
    assert selection is not None
    peer = _FakeKimiAcpPeer()
    exchange = owner.KimiAcpOneShotV1(
        b"safe task",
        selection.cwd or str(tmp_path / "private-run"),
        selection.mcp_servers,
    )

    exchange(peer)

    assert peer.requests[1]["params"] == {
        "cwd": str(selected_cwd),
        "mcpServers": expected_mcp,
        "additionalDirectories": [],
    }


def test_non_kimi_capability_option_is_rejected_before_file_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    owner = _load_owner()
    capability_file = tmp_path / "must-not-read.json"
    reads: list[Path] = []
    monkeypatch.setattr(
        owner,
        "read_kimi_capability_selection",
        lambda path: reads.append(path) or owner.KimiCapabilitySelectionV1(),
    )

    assert owner.launch(
        "claude", ["fixture", "--kimi-capabilities-file", str(capability_file)]
    ) != 0
    assert "E_EXTERNAL_LAUNCH_FLAGS_UNSAFE" in capsys.readouterr().err
    assert reads == []

    with pytest.raises(ValueError, match="^E_EXTERNAL_LAUNCH_FLAGS_UNSAFE$"):
        owner._prevalidate_policy_bound_external_launch(
            "grok",
            [
                "fixture",
                "--kimi-capabilities-file",
                str(capability_file),
                "--task-class",
                "review",
                "--role",
                "qa-engineer",
            ],
        )
    assert reads == []


def _write_fake_kimi_acp(tmp_path: Path, mode: str) -> Path:
    (tmp_path / "mode.txt").write_text(mode, encoding="ascii")
    script = tmp_path / "acp"
    script.write_text(
        """from __future__ import annotations

import json
import sys
import time
from pathlib import Path


root = Path.cwd()
mode = (root / "mode.txt").read_text(encoding="ascii")
methods = []
pending_prompt_id = None


def record(method):
    methods.append(method)
    (root / "methods.json").write_text(json.dumps(methods), encoding="utf-8")


def emit(message):
    sys.stdout.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\\n")
    sys.stdout.flush()


for line in sys.stdin.buffer:
    request = json.loads(line.decode("utf-8"))
    if "method" not in request:
        if pending_prompt_id is None:
            raise SystemExit(20)
        (root / "permission-response.json").write_text(
            json.dumps(request, ensure_ascii=True), encoding="utf-8"
        )
        emit({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "fake-session-1",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": "artifact\\nGATE: PASS\\n"},
                },
            },
        })
        emit({
            "jsonrpc": "2.0",
            "id": pending_prompt_id,
            "result": {"stopReason": "end_turn"},
        })
        pending_prompt_id = None
        continue
    method = request["method"]
    record(method)
    request_id = request.get("id")
    if method == "initialize":
        result = {"protocolVersion": 1, "agentCapabilities": {}}
    elif method == "session/new":
        if mode == "eof":
            raise SystemExit(0)
        result = {"sessionId": "fake-session-1"}
    elif method == "session/set_config_option":
        if request["params"] == {
            "sessionId": "fake-session-1",
            "configId": "model",
            "value": "kimi-code/k3",
        }:
            result = {
                "configOptions": [
                    {
                        "type": "select",
                        "id": "model",
                        "name": "Model",
                        "category": "model",
                        "currentValue": "kimi-code/k3",
                        "options": [{"value": "kimi-code/k3", "name": "K3"}],
                    }
                ]
            }
        elif request["params"] == {
            "sessionId": "fake-session-1",
            "configId": "thinking",
            "value": "high",
        }:
            result = {
                "configOptions": [
                    {
                        "type": "select",
                        "id": "thinking",
                        "name": "Thinking",
                        "category": "thinking",
                        "currentValue": "high",
                        "options": [
                            {"value": "low", "name": "Low"},
                            {"value": "high", "name": "High"},
                            {"value": "max", "name": "Max"},
                        ],
                    }
                ]
            }
        else:
            raise SystemExit(18)
    elif method == "session/prompt":
        text = request["params"]["prompt"][0]["text"]
        (root / "prompt.bin").write_bytes(text.encode("utf-8"))
        if mode == "cancel":
            (root / "cancel.ready").write_text("ready", encoding="ascii")
            continue
        if mode in {"permission", "permission-mismatch"}:
            emit({
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": "fake-session-1",
                    "update": {
                        "sessionUpdate": "tool_call",
                        "toolCallId": "1:tool-call-1",
                        "title": "Read",
                        "status": "in_progress",
                    },
                },
            })
            emit({
                "jsonrpc": "2.0",
                "id": "permission-rpc-1",
                "method": "session/request_permission",
                "params": {
                    "sessionId": "fake-session-1",
                    "options": [
                        {
                            "optionId": "deny-custom",
                            "name": "Reject",
                            "kind": (
                                "allow_once"
                                if mode == "permission-mismatch"
                                else "reject_once"
                            ),
                        }
                    ],
                    "toolCall": {
                        "toolCallId": "1:tool-call-1",
                        "title": "Read",
                    },
                },
            })
            pending_prompt_id = request_id
            continue
        if mode == "paced-overflow":
            for _ in range(7):
                emit({
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": "fake-session-1",
                        "update": {
                            "sessionUpdate": "agent_thought_chunk",
                            "content": {"type": "text", "text": "x" * 180000},
                        },
                    },
                })
            time.sleep(0.5)
        if mode == "stderr-overflow":
            sys.stderr.write("e" * (1024 * 1024 + 1))
            sys.stderr.flush()
            time.sleep(0.5)
        answer = (
            "x" * 1024 + "\\nGATE: PASS\\n"
            if mode == "answer-oversize"
            else "artifact\\nGATE: PASS\\n"
        )
        emit({
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {
                "sessionId": "fake-session-1",
                "update": {
                    "sessionUpdate": "agent_message_chunk",
                    "content": {"type": "text", "text": answer},
                },
            },
        })
        result = {"stopReason": "end_turn"}
    elif method == "session/cancel":
        continue
    elif method in {"session/close", "session/delete"}:
        result = {}
    else:
        raise SystemExit(19)
    emit({"jsonrpc": "2.0", "id": request_id, "result": result})
    if method == "session/delete":
        raise SystemExit(7 if mode == "nonzero" else 0)
""",
        encoding="utf-8",
    )
    return script


def _run_fake_kimi_acp(
    tmp_path: Path,
    mode: str,
    body: bytes,
    *,
    result_max_bytes: int = 1024 * 1024,
    continue_after_stdout_capture_limit: bool = True,
):
    owner = _load_owner()
    _write_fake_kimi_acp(tmp_path, mode)
    executable = Path(sys.executable).resolve()
    runner = owner.ProcessRunnerV1()
    sink = runner.mint_memory_capture_sink()
    environment = [
        owner.EnvironmentRowV1(name, os.environ[name])
        for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP")
        if name in os.environ
    ]
    environment.append(owner.EnvironmentRowV1("PYTHONUNBUFFERED", "1"))
    request = owner.ProcessRequestV1(
        schema_version=1,
        argv=(str(executable), "acp"),
        resolved_executable=executable,
        cwd=str(tmp_path),
        environment=tuple(environment),
        stdin_bytes=None,
        deadline_monotonic=__import__("time").monotonic() + 5.0,
        capture_policy=owner.CapturePolicyV1(
            "fake-kimi-acp-v1", 1024 * 1024, 0, 0, 64 * 1024
        ),
        capture_sink_binding=sink,
        settle_policy=owner.SettlePolicyV1(5.0),
        cancellation_probe=(
            (lambda: (tmp_path / "cancel.ready").is_file())
            if mode == "cancel"
            else None
        ),
        windows_argv_profile_id=owner.KIMI_WINDOWS_PROFILE_V1.profile_id,
        expected_executable_binding=owner.ExecutableBindingV1(
            str(executable),
            executable.stat().st_size,
            hashlib.sha256(executable.read_bytes()).hexdigest(),
        ),
    )
    exchange = owner.KimiAcpOneShotV1(body, str(tmp_path))
    object.__setattr__(exchange, "result_max_bytes", result_max_bytes)
    dialogue = owner.ProcessDialogueV1(
        owner.KIMI_WINDOWS_PROFILE_V1.profile_id, exchange
    )
    object.__setattr__(
        dialogue,
        "continue_after_stdout_capture_limit",
        continue_after_stdout_capture_limit,
    )
    try:
        result = runner.run(
            request,
            dialogue=dialogue,
        )
    finally:
        close_result = runner.close()
    return exchange, result, close_result


@pytest.mark.skipif(os.name != "nt", reason="Windows finite Kimi ACP process contract")
def test_fake_kimi_acp_process_preserves_literals_and_settles(tmp_path: Path) -> None:
    body = (
        "set(ROOT ${CMAKE_SOURCE_DIR})\r\n"
        "echo ${x} $USER $$ $$$$\n"
        "embedded:\x00; unicode: Привет 🌍"
    ).encode("utf-8")

    exchange, result, close_result = _run_fake_kimi_acp(tmp_path, "success", body)

    assert (tmp_path / "prompt.bin").read_bytes() == body
    assert exchange.result_bytes == b"artifact\nGATE: PASS\n"
    assert result.outcome == "success"
    assert result.target_exit_code == 0
    assert result.failure_id is None
    assert result.resources_closed is True
    assert result.tree.tree_empty is True
    assert close_result.outcome == "closed"


@pytest.mark.skipif(os.name != "nt", reason="Windows finite Kimi ACP process contract")
def test_fake_kimi_acp_process_rejects_eof_and_settles(tmp_path: Path) -> None:
    _exchange, result, close_result = _run_fake_kimi_acp(
        tmp_path, "eof", b"safe task"
    )

    assert result.failure_id == "PSV1-KIMI-ACP-PROTOCOL"
    assert result.resources_closed is True
    assert result.tree.tree_empty is True
    assert close_result.outcome == "closed"


@pytest.mark.skipif(os.name != "nt", reason="Windows finite Kimi ACP process contract")
def test_fake_kimi_acp_process_preserves_nonzero_exit(tmp_path: Path) -> None:
    exchange, result, close_result = _run_fake_kimi_acp(
        tmp_path, "nonzero", b"safe task"
    )

    assert exchange.result_bytes == b"artifact\nGATE: PASS\n"
    assert result.outcome == "child-failure"
    assert result.target_exit_code == 7
    assert result.resources_closed is True
    assert result.tree.tree_empty is True
    assert close_result.outcome == "closed"


@pytest.mark.skipif(os.name != "nt", reason="Windows finite Kimi ACP process contract")
def test_fake_kimi_acp_process_cancels_then_closes_deletes_and_settles(
    tmp_path: Path,
) -> None:
    _exchange, result, close_result = _run_fake_kimi_acp(
        tmp_path, "cancel", b"safe task"
    )

    methods = json.loads((tmp_path / "methods.json").read_text(encoding="utf-8"))
    assert methods == [
        "initialize",
        "session/new",
        "session/set_config_option",
        "session/set_config_option",
        "session/prompt",
        "session/cancel",
        "session/close",
        "session/delete",
    ]
    assert result.failure_id == "PSV1-CANCELLED"
    assert result.cancelled is True
    assert result.resources_closed is True
    assert result.tree.tree_empty is True
    assert close_result.outcome == "closed"


@pytest.mark.skipif(os.name != "nt", reason="Windows finite Kimi ACP process contract")
def test_fake_kimi_acp_permission_response_and_observation_settle(tmp_path: Path) -> None:
    exchange, result, close_result = _run_fake_kimi_acp(
        tmp_path, "permission", b"safe task"
    )

    response = json.loads(
        (tmp_path / "permission-response.json").read_text(encoding="utf-8")
    )
    assert response == {
        "jsonrpc": "2.0",
        "id": "permission-rpc-1",
        "result": {
            "outcome": {"outcome": "selected", "optionId": "deny-custom"}
        },
    }
    assert exchange.observed_receipt() == {
        "toolCalls": [
            {"id": "1:tool-call-1", "title": "Read", "status": "in_progress"}
        ],
        "permissionDecisions": [
            {"id": "1:tool-call-1", "title": "Read", "decision": "reject"}
        ],
    }
    assert result.outcome == "success"
    assert result.resources_closed is True
    assert result.tree.tree_empty is True
    assert close_result.outcome == "closed"


@pytest.mark.skipif(os.name != "nt", reason="Windows finite Kimi ACP process contract")
def test_fake_kimi_acp_permission_option_mismatch_reaps_process(tmp_path: Path) -> None:
    _exchange, result, close_result = _run_fake_kimi_acp(
        tmp_path, "permission-mismatch", b"safe task"
    )

    assert result.failure_id == "PSV1-KIMI-ACP-PROTOCOL"
    assert result.resources_closed is True
    assert result.tree.tree_empty is True
    assert close_result.outcome == "closed"


@pytest.mark.skipif(os.name != "nt", reason="Windows finite Kimi ACP process contract")
def test_fake_kimi_acp_paced_stdout_overflow_drains_to_complete_answer(
    tmp_path: Path,
) -> None:
    exchange, result, close_result = _run_fake_kimi_acp(
        tmp_path, "paced-overflow", b"safe task"
    )

    assert exchange.result_bytes == b"artifact\nGATE: PASS\n"
    assert result.outcome == "success"
    assert result.failure_id is None
    assert result.target_exit_code == 0
    assert result.stdout.truncated is True
    assert result.stdout.observed_bytes > 1024 * 1024
    assert result.stdin.complete is True
    assert result.resources_closed is True
    assert result.tree.tree_empty is True
    assert close_result.outcome == "closed"


@pytest.mark.skipif(os.name != "nt", reason="Windows finite Kimi ACP process contract")
def test_fake_kimi_acp_paced_stdout_overflow_is_fatal_by_default(
    tmp_path: Path,
) -> None:
    exchange, result, close_result = _run_fake_kimi_acp(
        tmp_path,
        "paced-overflow",
        b"safe task",
        continue_after_stdout_capture_limit=False,
    )

    assert exchange.result_bytes == b""
    assert result.failure_id == "PSV1-CAPTURE-LIMIT"
    assert result.stdout.truncated is True
    assert result.resources_closed is True
    assert result.tree.tree_empty is True
    assert close_result.outcome == "closed"


@pytest.mark.skipif(os.name != "nt", reason="Windows finite Kimi ACP process contract")
def test_fake_kimi_acp_stderr_overflow_remains_fatal(tmp_path: Path) -> None:
    exchange, result, close_result = _run_fake_kimi_acp(
        tmp_path, "stderr-overflow", b"safe task"
    )

    assert exchange.result_bytes == b""
    assert result.failure_id == "PSV1-CAPTURE-LIMIT"
    assert result.stderr.truncated is True
    assert result.resources_closed is True
    assert result.tree.tree_empty is True
    assert close_result.outcome == "closed"


@pytest.mark.skipif(os.name != "nt", reason="Windows finite Kimi ACP process contract")
def test_fake_kimi_acp_oversize_answer_fails_and_reaps_process(tmp_path: Path) -> None:
    exchange, result, close_result = _run_fake_kimi_acp(
        tmp_path, "answer-oversize", b"safe task", result_max_bytes=64
    )

    assert exchange.result_bytes == b""
    assert result.failure_id == "PSV1-KIMI-ACP-PROTOCOL"
    assert result.resources_closed is True
    assert result.tree.tree_empty is True
    assert close_result.outcome == "closed"


@pytest.mark.parametrize("mutation", ("rewrite", "grow", "replace", "remove"))
def test_kimi_capability_snapshot_rejects_drift_during_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    owner = _load_owner()
    path = tmp_path / "capabilities.json"
    _write_kimi_capabilities(path)
    original = path.read_bytes()
    fdopen = owner.os.fdopen

    class MutatingReader:
        def __init__(self, descriptor, mode):
            self.stream = fdopen(descriptor, mode)

        def __enter__(self):
            self.stream.__enter__()
            return self

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            raw = self.stream.read(size)
            if mutation in {"rewrite", "grow"}:
                path.write_bytes(original if mutation == "rewrite" else original + b" ")
                stamp = path.stat()
                os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
            return raw

        def seek(self, *args):
            return self.stream.seek(*args)

        def __exit__(self, *args):
            result = self.stream.__exit__(*args)
            if mutation == "replace":
                replacement = path.with_suffix(".replacement")
                replacement.write_bytes(original)
                os.replace(replacement, path)
            elif mutation == "remove":
                path.unlink()
            return result

    monkeypatch.setattr(owner.os, "fdopen", MutatingReader)
    with pytest.raises(ValueError, match="^E_KIMI_CAPABILITIES_INVALID$"):
        owner.read_kimi_capability_selection(path)


def test_kimi_capability_snapshot_rejects_same_metadata_rewrite_between_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    path = tmp_path / "capabilities.json"
    _write_kimi_capabilities(path, tools=["Read"])
    original = path.read_bytes()
    changed = original.replace(b'"Read"', b'"Bash"')
    assert changed != original and len(changed) == len(original)

    path_snapshot = path.lstat()
    original_lstat = owner.Path.lstat
    original_fstat = owner.os.fstat
    original_fdopen = owner.os.fdopen
    frozen_descriptor_metadata = {}
    reads = []

    def stable_lstat(candidate: Path):
        if Path(candidate) == path:
            return path_snapshot
        return original_lstat(candidate)

    def stable_fstat(descriptor: int):
        observed = original_fstat(descriptor)
        return frozen_descriptor_metadata.setdefault("value", observed)

    class RewritingReader:
        def __init__(self, descriptor, mode):
            self.stream = original_fdopen(descriptor, mode)

        def __enter__(self):
            self.stream.__enter__()
            return self

        def fileno(self):
            return self.stream.fileno()

        def read(self, size=-1):
            raw = self.stream.read(size)
            reads.append(raw)
            if len(reads) == 1:
                path.write_bytes(changed)
                os.utime(
                    path,
                    ns=(path_snapshot.st_atime_ns, path_snapshot.st_mtime_ns),
                )
            return raw

        def seek(self, *args):
            return self.stream.seek(*args)

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

    monkeypatch.setattr(owner.Path, "lstat", stable_lstat)
    monkeypatch.setattr(owner.os, "fstat", stable_fstat)
    monkeypatch.setattr(owner.os, "fdopen", RewritingReader)
    monkeypatch.setattr(
        owner,
        "_open_kimi_capability_reader",
        lambda candidate: os.open(
            candidate,
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
        ),
    )

    with pytest.raises(ValueError, match="^E_KIMI_CAPABILITIES_INVALID$"):
        owner.read_kimi_capability_selection(path)

    assert len(reads) == 2


@pytest.mark.skipif(os.name != "nt", reason="Windows capability writer exclusion")
def test_kimi_capability_snapshot_excludes_windows_writers(tmp_path: Path) -> None:
    owner = _load_owner()
    path = tmp_path / "capabilities.json"
    _write_kimi_capabilities(path, tools=["Read"])
    original = path.read_bytes()
    descriptor = owner._open_kimi_capability_reader(path)
    replacement = path.with_suffix(".replacement")
    replacement.write_bytes(original.replace(b'"Read"', b'"Bash"'))

    try:
        with pytest.raises(OSError):
            path.write_bytes(replacement.read_bytes())
        assert path.read_bytes() == original
        with pytest.raises(OSError):
            os.replace(replacement, path)
        assert path.read_bytes() == original
    finally:
        os.close(descriptor)
        replacement.unlink(missing_ok=True)


@pytest.mark.parametrize("name", ("DB_DSN", "X-Service-Key", "apiKey", "authenticationToken"))
@pytest.mark.parametrize("carrier", ("env", "headers"))
def test_kimi_custom_selected_value_cannot_escape_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], name: str, carrier: str,
) -> None:
    owner = _load_owner()
    canary = "synthetic-selected-value"
    server = owner.KimiMcpServerV1(
        name="fixture", **{carrier: (owner.KimiNameValueV1(name, canary),)}
    )
    selection = owner.KimiCapabilitySelectionV1(mcp_servers=(server,))
    code, payload, _, lifecycle = _finalize_kimi(
        owner, tmp_path, monkeypatch, capsys,
        stdout=canary.encode() + b"\nGATE: PASS\n", stderr=b"",
        capabilities=selection, credential_needles=owner._kimi_mcp_credential_needles(selection),
    )
    assert code != 0
    assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
    assert canary not in json.dumps(payload)
    assert canary not in (tmp_path / "kimi-terminal.receipt").read_text(encoding="utf-8")
    assert not lifecycle.run_dir.exists()


@pytest.mark.parametrize("value", ('synthetic-"quote', "synthetic-\\slash", "synthetic-\u03c0"))
def test_kimi_serialized_metadata_cannot_escape_credential_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], value: str,
) -> None:
    owner = _load_owner()
    selection = owner.KimiCapabilitySelectionV1(
        tools=(value,), mcp_servers=(owner.KimiMcpServerV1(
            name="fixture", env=(owner.KimiNameValueV1("TOKEN", value),),
        ),),
    )
    code, payload, _, lifecycle = _finalize_kimi(
        owner, tmp_path, monkeypatch, capsys, stdout=b"safe\nGATE: PASS\n", stderr=b"",
        capabilities=selection, credential_needles=owner._kimi_mcp_credential_needles(selection),
    )
    assert code != 0
    assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
    assert "selected" not in payload and not lifecycle.run_dir.exists()
    public = json.dumps(payload)
    receipt = (tmp_path / "kimi-terminal.receipt").read_text(encoding="utf-8")
    for encoding in (False, True):
        escaped = json.dumps(value, ensure_ascii=encoding)[1:-1]
        assert escaped not in public and escaped not in receipt


@pytest.mark.parametrize("url", (
    "https://fixture:synthetic%2Durl%2Dsecret@example.invalid/mcp",
    "https://example.invalid/mcp?custom=synthetic%2Durl%2Dsecret",
    "https://example.invalid/mcp?synthetic%2Durl%2Dsecret",
    "https://example.invalid/mcp?synthetic-url-secret",
    "https://example.invalid/synthetic%2Durl%2Dsecret/mcp",
    "https://example.invalid/synthetic-url-secret/mcp",
    "https://example.invalid/mcp#synthetic%2Durl%2Dsecret",
    "https://example.invalid/mcp?&synthetic%2Durl%2Dsecret&",
))
def test_kimi_url_credential_cannot_escape_terminal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], url: str,
) -> None:
    owner = _load_owner()
    selection = owner.KimiCapabilitySelectionV1(mcp_servers=(
        owner.KimiMcpServerV1(name="fixture", transport="http", url=url),
    ))
    code, payload, _, lifecycle = _finalize_kimi(
        owner, tmp_path, monkeypatch, capsys,
        stdout=b"synthetic-url-secret\nGATE: PASS\n", stderr=b"",
        capabilities=selection, credential_needles=owner._kimi_mcp_credential_needles(selection),
    )
    assert code != 0
    assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
    assert "synthetic-url-secret" not in json.dumps(payload)
    assert "synthetic-url-secret" not in (tmp_path / "kimi-terminal.receipt").read_text(encoding="utf-8")
    assert not lifecycle.run_dir.exists()


@pytest.mark.parametrize("carrier", ("environment_url", "encoded_query"))
def test_kimi_structured_selected_credential_surfaces_are_guarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], carrier: str,
) -> None:
    owner = _load_owner()
    canary = "synthetic-extra-value"
    options = {
        "environment_url": {"env": (owner.KimiNameValueV1(
            "DB_DSN", "https://fixture:" + canary + "@example.invalid/db"
        ),)},
        "encoded_query": {"url": "https://example.invalid/mcp?custom=synthetic%2Dextra%2Dvalue"},
    }
    echo = "synthetic%2Dextra%2Dvalue" if carrier == "encoded_query" else canary
    selection = owner.KimiCapabilitySelectionV1(mcp_servers=(
        owner.KimiMcpServerV1(name="fixture", **options[carrier]),
    ))
    code, payload, _, lifecycle = _finalize_kimi(
        owner, tmp_path, monkeypatch, capsys, stdout=echo.encode() + b"\nGATE: PASS\n", stderr=b"",
        capabilities=selection, credential_needles=owner._kimi_mcp_credential_needles(selection),
    )
    assert code != 0
    assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
    assert echo not in json.dumps(payload)
    assert echo not in (tmp_path / "kimi-terminal.receipt").read_text(encoding="utf-8")
    assert not lifecycle.run_dir.exists()


@pytest.mark.parametrize('carrier', ('arguments', 'public_url', 'public_controls'))
def test_benign_selected_controls_succeed(tmp_path, monkeypatch, capsys, carrier):
    owner = _load_owner()
    url = 'https://example.invalid/mcp'
    options = {
        'arguments': {'args': ('--port', '8080', '--flag', '1')},
        'public_url': {'url': url},
        'public_controls': {
            'env': (owner.KimiNameValueV1('PATH', 'public-value'),),
            'headers': (owner.KimiNameValueV1('Accept-Language', 'en'),),
        },
    }
    selection = owner.KimiCapabilitySelectionV1(mcp_servers=(
        owner.KimiMcpServerV1(name='fixture', **options[carrier]),
    ))
    output = url if carrier == 'public_url' else 'safe public-value en'
    code, payload, _, lifecycle = _finalize_kimi(
        owner, tmp_path, monkeypatch, capsys,
        stdout=output.encode()+b'\nGATE: PASS\n', stderr=b'',
        capabilities=selection, credential_needles=owner._kimi_mcp_credential_needles(selection),
    )
    assert code == 0, payload
    assert payload['gate'] == 'PASS'
    assert not lifecycle.run_dir.exists()


@pytest.mark.parametrize("invalid", (
    "https://example.invalid/mcp?custom=%FF", "https://[::1", "synthetic-\ud800", "synthetic-\x00",
))
def test_kimi_unscannable_selection_has_only_minimal_prelaunch_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], invalid: str,
) -> None:
    owner = _load_owner()
    canary = "synthetic-valid-private-value"
    selection = owner.KimiCapabilitySelectionV1(
        tools=(canary,), mcp_servers=(owner.KimiMcpServerV1(
            name="fixture", env=(owner.KimiNameValueV1("X-Custom", canary),
                                 owner.KimiNameValueV1("X-Other", invalid)),
        ),),
    )
    receipt_path = tmp_path / "minimal.receipt"
    control = owner.Control(terminal_receipt=receipt_path, kimi_capabilities=selection)
    prevalidated = owner.PolicyBoundLaunch(
        control, "fixture", (), "kimi-code/k3", "high",
        owner.ExternalRoleProvenance("none", "none"), None,
    )
    monkeypatch.setattr(owner, "_resolve_launch_provider_command", lambda *_: (["fixture"], None))
    monkeypatch.setattr(owner, "resolve_provider_auth_configuration", lambda *_: SimpleNamespace(needles=()))
    monkeypatch.setattr(owner.RunCaptureLifecycle, "create", classmethod(
        lambda *_: pytest.fail("invalid credential selection reached capture/provider setup")
    ))
    with owner.ReservedExternalRunV1(owner.TerminalReceiptV1.reserve(receipt_path)) as reserved:
        code = owner._launch_with_runner(
            "kimi", [], object(), prevalidated=prevalidated, reserved_run=reserved,
        )
    public = capsys.readouterr().out
    payload = json.loads(public.split("=", 1)[1])
    assert code == 1
    assert payload["token"] == "UNVERIFIED:E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE"
    assert "selected" not in payload and "observed" not in payload
    assert canary not in public and canary not in receipt_path.read_text(encoding="utf-8")
    assert payload["cleanupStatus"] == "complete"


def test_kimi_unchanged_snapshot_allows_distinct_handle_and_path_ctime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = _load_owner()
    path = tmp_path / "capabilities.json"
    _write_kimi_capabilities(path, tools=["ReadFile"])
    real_fstat = owner.os.fstat

    def descriptor_metadata(descriptor):
        metadata = real_fstat(descriptor)
        fields = {name: getattr(metadata, name) for name in dir(metadata) if name.startswith("st_")}
        fields["st_ctime_ns"] += 2_000_000_000
        return SimpleNamespace(**fields)

    monkeypatch.setattr(owner.os, "fstat", descriptor_metadata)
    assert owner.read_kimi_capability_selection(path).tools == ("ReadFile",)
