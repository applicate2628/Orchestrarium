from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER_PATH = ROOT / "scripts" / "provider_prompt.py"
WRAPPER_PATH = ROOT / "scripts" / "invoke-kimi-prompt.py"
INSTALLER_PATH = ROOT / "scripts" / "production_installer.py"
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


def test_kimi_maintenance_modes_never_launch_provider(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    owner = _load_owner()
    enrolled: list[tuple[Path, Path, bool]] = []
    verified = [False]

    def enroll(home: Path, runtime_root: Path, *, dry_run: bool) -> None:
        enrolled.append((home, runtime_root, dry_run))

    def verify() -> list[str]:
        verified[0] = True
        return [r"C:\fixed\kimi.exe"]

    def forbidden_launch(_provider: str, _argv: list[str]) -> int:
        raise AssertionError("maintenance mode reached provider launch")

    monkeypatch.setattr(owner, "enroll_kimi_executable", enroll)
    monkeypatch.setattr(owner, "verify_kimi_enrollment", verify)
    monkeypatch.setattr(owner, "launch", forbidden_launch)

    assert owner.kimi_main(["--enroll-executable"]) == 0
    assert len(enrolled) == 1
    assert enrolled[0][0].is_absolute()
    assert enrolled[0][1].name == "kimi"
    assert enrolled[0][2] is False
    assert owner.kimi_main(["--verify-enrollment"]) == 0
    assert verified == [True]
    assert "KIMI-EXECUTABLE-ENROLLMENT: PASS" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    (
        ["--enroll-executable", "topic"],
        ["--verify-enrollment", "--enroll-executable"],
        ["topic", "--verify-enrollment"],
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


def test_kimi_profile_is_fixed_and_has_no_native_effort_control() -> None:
    owner = _load_owner()
    assert owner.resolved_profile("kimi", []) == ([], "kimi-code/k3", "unsupported")
    with pytest.raises(ValueError, match="E_KIMI_PROFILE_FIXED"):
        owner.resolved_profile("kimi", ["--model", "other"])


def test_kimi_file_reference_argv_is_exact(tmp_path: Path) -> None:
    owner = _load_owner()
    agent = tmp_path / "agent.md"
    skills = tmp_path / "empty-skills"
    agent.write_text(
        "---\nname: orchestrarium-bundle-reviewer\n"
        "description: Reviews only the context bundled in this file\n"
        "tools: []\nsubagents: []\n---\nGATE: PASS\n",
        encoding="utf-8",
    )
    skills.mkdir()
    assert owner.kimi_provider_args(agent, skills) == [
        "--agent-file",
        str(agent.resolve()),
        "--skills-dir",
        str(skills.resolve()),
        "--model",
        "kimi-code/k3",
        "--output-format",
        "text",
        "--prompt",
        owner.KIMI_WINDOWS_PROFILE_V1.constant_prompt,
    ]


def test_kimi_command_resolution_ignores_ambient_binary_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    executable = tmp_path / "kimi.exe"
    executable.write_bytes(b"synthetic")
    monkeypatch.setenv("KIMI_BIN", str(executable))
    assert owner.resolve_provider_command("kimi") is None


def test_kimi_bundle_rejects_ambient_template_variables(tmp_path: Path) -> None:
    owner = _load_owner()
    with pytest.raises(ValueError, match="E_KIMI_BUNDLE_TEMPLATE_INVALID"):
        owner.kimi_agent_bundle(b"Review ${cwd}", tmp_path)


def test_kimi_bundle_is_no_tools_and_no_subagents(tmp_path: Path) -> None:
    owner = _load_owner()
    task = b"Review the sealed context."
    agent, skills = owner.kimi_agent_bundle(task, tmp_path)
    assert skills.is_dir() and not tuple(skills.iterdir())
    expected = (
        "---\nname: orchestrarium-bundle-reviewer\n"
        "description: Reviews only the context bundled in this file\n"
        "tools: []\nsubagents: []\n---\n\n"
    )
    text = agent.read_text(encoding="utf-8")
    assert text.startswith(expected)
    assert text == (
        expected
        + owner.KIMI_AGENT_BUNDLE_PREAMBLE.decode("utf-8")
        + task.decode("utf-8")
        + owner.KIMI_AGENT_BUNDLE_EPILOGUE.decode("utf-8")
    )
    assert "tools: []" in text and "subagents: []" in text


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
) -> SimpleNamespace:
    return SimpleNamespace(
        resources_closed=settled,
        tree=SimpleNamespace(tree_empty=settled, direct_reaped=settled),
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
    code = owner.finalize_run(
        control,
        "kimi",
        "kimi-code/k3",
        "unsupported",
        "fixture",
        "launch-fixture" if with_ledger else "",
        lifecycle,
        exit_code,
        capture,
        cancelled=cancelled,
        role_provenance=provenance,
        raw_stdout=stdout,
        raw_stderr=stderr,
        process_result=process_result or process,
        runner=object() if with_ledger else None,
    )
    payload = owner.parse_provider_result(capsys.readouterr().out)
    notes = (
        ledger_calls[0][ledger_calls[0].index("--notes") + 1]
        if ledger_calls
        else ""
    )
    return code, payload, [notes], lifecycle


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

    assert code == 0
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

    code = owner.finalize_run(
        owner.Control(),
        "claude",
        "opus",
        "xhigh",
        "fixture",
        "",
        lifecycle,
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


def test_kimi_wrapper_has_no_auth_storage_contract() -> None:
    source = OWNER_PATH.read_text(encoding="utf-8")
    forbidden = (
        "_kimi_sanitized_runtime_home",
        "KIMI_CODE_HOME",
        "access_token",
        "refresh_token",
        "expires_at",
        "oauth_host",
        "E_KIMI_AUTH_STORAGE_INVALID",
    )
    assert all(token not in source for token in forbidden)


def test_kimi_profile_identifier_has_one_production_owner() -> None:
    source = (ROOT / "scripts" / "process_supervision" / "process_runner.py").read_text(
        encoding="utf-8"
    )
    assert source.count('"kimi-sealed-bundle-text-v1"') == 1
    assert source.count('"--agent-file"') == 1


def test_runtime_pin_is_restored_after_injected_post_enrollment_failure(
    tmp_path: Path,
) -> None:
    installer = _load_installer()
    pin = tmp_path / "runtime" / "kimi" / "executable-binding-v1.json"
    pin.parent.mkdir(parents=True)
    before = b'{"accepted":"prior"}\n'
    pin.write_bytes(before)

    with pytest.raises(RuntimeError, match="injected"):
        with installer._InstallTransaction([pin], enabled=True):
            pin.write_bytes(b'{"accepted":"new"}\n')
            raise RuntimeError("injected post-enrollment failure")

    assert pin.read_bytes() == before


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


def test_kimi_enrollment_drift_preserves_specific_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    user_home = tmp_path / "user"
    runtime = user_home / ".codex" / "orchestrarium-runtime" / "kimi"
    runtime.mkdir(parents=True)
    executable = tmp_path / "kimi.exe"
    executable.write_bytes(b"changed-release")
    (runtime / "executable-binding-v1.json").write_text(
        json.dumps(
            {
                "schema": owner.KIMI_EXECUTABLE_BINDING_SCHEMA_V1,
                "path": str(executable.resolve()),
                "sha256": "0" * 64,
                "size": executable.stat().st_size,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("USERPROFILE", str(user_home))

    with pytest.raises(ValueError, match="^E_KIMI_EXECUTABLE_BINDING_DRIFT$"):
        owner.resolve_enrolled_kimi_command()


def test_missing_kimi_binding_names_exact_wrapper_enrollment_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    user_home = tmp_path / "user"
    user_home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(user_home))
    expected = subprocess.list2cmdline(
        [sys.executable, str(WRAPPER_PATH.resolve()), "--enroll-executable"]
    )

    with pytest.raises(ValueError) as failure:
        owner.resolve_enrolled_kimi_command()

    assert str(failure.value) == (
        f"E_KIMI_EXECUTABLE_BINDING_INVALID: run {expected}"
    )


def test_kimi_binding_owner_enrolls_replays_and_refuses_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    installer = _load_installer()
    user_home = tmp_path / "user"
    executable = user_home / ".kimi-code" / "bin" / "kimi.exe"
    executable.parent.mkdir(parents=True)
    payload = b"synthetic-kimi-release"
    executable.write_bytes(payload)
    runtime_root = user_home / ".codex" / "orchestrarium-runtime" / "kimi"
    profile = SimpleNamespace(
        expected_size=len(payload),
        accepted_sha256=hashlib.sha256(payload).hexdigest(),
    )
    monkeypatch.setattr(owner, "KimiWindowsProfileV1", profile)

    owner.enroll_kimi_executable(user_home, runtime_root, dry_run=False)
    pin = runtime_root / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V1
    expected_binding = {
        "path": str(executable.resolve()),
        "schema": owner.KIMI_EXECUTABLE_BINDING_SCHEMA_V1,
        "sha256": profile.accepted_sha256,
        "size": len(payload),
    }
    assert json.loads(pin.read_text(encoding="utf-8")) == expected_binding

    replay_bytes = pin.read_bytes()
    replay_metadata = pin.stat()
    replay_identity = (
        replay_metadata.st_dev,
        replay_metadata.st_ino,
        replay_metadata.st_size,
        replay_metadata.st_mtime_ns,
    )
    monkeypatch.setattr(
        owner.tempfile,
        "mkstemp",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("exact replay attempted temporary publication")
        ),
    )
    monkeypatch.setattr(
        owner.os,
        "link",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("exact replay attempted create-only publication")
        ),
    )
    owner.enroll_kimi_executable(user_home, runtime_root, dry_run=False)
    replay_after = pin.stat()
    assert pin.read_bytes() == replay_bytes
    assert (
        replay_after.st_dev,
        replay_after.st_ino,
        replay_after.st_size,
        replay_after.st_mtime_ns,
    ) == replay_identity
    assert not tuple(runtime_root.glob(".kimi-binding.*.tmp"))

    pin.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="^E_KIMI_ENROLLMENT_DRIFT"):
        owner.enroll_kimi_executable(user_home, runtime_root, dry_run=False)

    installer_call: list[tuple[Path, Path, bool]] = []
    monkeypatch.setattr(
        installer,
        "enroll_kimi_executable",
        lambda home, root, *, dry_run: installer_call.append(
            (home, root, dry_run)
        ),
    )
    installer._enroll_kimi_executable(user_home, runtime_root, dry_run=True)
    assert installer_call == [(user_home, runtime_root, True)]


def test_kimi_enrollment_preserves_destination_created_at_placement_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    user_home = tmp_path / "user"
    executable = user_home / ".kimi-code" / "bin" / "kimi.exe"
    executable.parent.mkdir(parents=True)
    executable_payload = b"synthetic-kimi-release"
    executable.write_bytes(executable_payload)
    runtime_root = user_home / ".codex" / "orchestrarium-runtime" / "kimi"
    profile = SimpleNamespace(
        expected_size=len(executable_payload),
        accepted_sha256=hashlib.sha256(executable_payload).hexdigest(),
    )
    monkeypatch.setattr(owner, "KimiWindowsProfileV1", profile)
    pin = runtime_root / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V1
    competing_payload = b"concurrent binding owner\n"
    real_replace = owner.os.replace
    real_link = owner.os.link

    def race_replace(source: Path, destination: Path) -> None:
        Path(destination).write_bytes(competing_payload)
        real_replace(source, destination)

    def race_link(source: Path, destination: Path) -> None:
        Path(destination).write_bytes(competing_payload)
        real_link(source, destination)

    monkeypatch.setattr(owner.os, "replace", race_replace)
    monkeypatch.setattr(owner.os, "link", race_link)

    with pytest.raises(ValueError, match="^E_KIMI_ENROLLMENT_DRIFT"):
        owner.enroll_kimi_executable(user_home, runtime_root, dry_run=False)

    assert pin.read_bytes() == competing_payload
    assert not tuple(runtime_root.glob(".kimi-binding.*.tmp"))


def test_kimi_enrollment_preserves_dangling_binding_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    user_home = tmp_path / "user"
    executable = user_home / ".kimi-code" / "bin" / "kimi.exe"
    executable.parent.mkdir(parents=True)
    executable_payload = b"synthetic-kimi-release"
    executable.write_bytes(executable_payload)
    runtime_root = user_home / ".codex" / "orchestrarium-runtime" / "kimi"
    runtime_root.mkdir(parents=True)
    profile = SimpleNamespace(
        expected_size=len(executable_payload),
        accepted_sha256=hashlib.sha256(executable_payload).hexdigest(),
    )
    monkeypatch.setattr(owner, "KimiWindowsProfileV1", profile)
    pin = runtime_root / owner.KIMI_EXECUTABLE_BINDING_FILENAME_V1
    missing_target = tmp_path / "missing-binding-target.json"
    try:
        pin.symlink_to(missing_target)
    except OSError as exc:
        pytest.skip(f"file symlink creation unavailable: {exc}")

    with pytest.raises(
        ValueError, match="^E_KIMI_ENROLLMENT_INVALID: existing pin$"
    ):
        owner.enroll_kimi_executable(user_home, runtime_root, dry_run=False)

    assert pin.is_symlink()
    assert pin.resolve(strict=False) == missing_target.resolve(strict=False)
    assert not missing_target.exists()
    assert not tuple(runtime_root.glob(".kimi-binding.*.tmp"))


def test_verify_kimi_enrollment_detects_same_size_content_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    user_home = tmp_path / "user"
    executable = user_home / ".kimi-code" / "bin" / "kimi.exe"
    executable.parent.mkdir(parents=True)
    payload = b"release-A"
    executable.write_bytes(payload)
    runtime_root = user_home / ".codex" / "orchestrarium-runtime" / "kimi"
    profile = SimpleNamespace(
        expected_size=len(payload),
        accepted_sha256=hashlib.sha256(payload).hexdigest(),
    )
    monkeypatch.setattr(owner, "KimiWindowsProfileV1", profile)
    monkeypatch.setenv("USERPROFILE", str(user_home))
    owner.enroll_kimi_executable(user_home, runtime_root, dry_run=False)

    assert owner.verify_kimi_enrollment() == [str(executable.resolve())]
    executable.write_bytes(b"release-B")
    with pytest.raises(ValueError, match="^E_KIMI_EXECUTABLE_BINDING_DRIFT$"):
        owner.verify_kimi_enrollment()


def test_kimi_release_profile_pins_official_039_windows_x64_identity() -> None:
    owner = _load_owner()

    assert owner.KIMI_WINDOWS_PROFILE_V1.expected_size == 151532032
    assert owner.KIMI_WINDOWS_PROFILE_V1.accepted_sha256 == (
        "9ddec448e6de4cacb5c4a07bf57c1909e699a0589c39eda851afdaab47b22dd2"
    )
    assert owner.KIMI_WINDOWS_PROFILE_V1.argv_shape == (
        "--agent-file",
        None,
        "--skills-dir",
        None,
        "--model",
        "kimi-code/k3",
        "--output-format",
        "text",
        "--prompt",
        owner.KIMI_WINDOWS_PROFILE_V1.constant_prompt,
    )
