from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER_PATH = ROOT / "scripts" / "provider_prompt.py"
WRAPPER_PATH = ROOT / "scripts" / "invoke-kimi-prompt.py"
INSTALLER_PATH = ROOT / "scripts" / "production_installer.py"
K3_METADATA_TOML = (
    'max_context_size = 1048576\n'
    'capabilities = ["thinking", "always_thinking", "image_in", "video_in", "tool_use"]\n'
    'display_name = "K3"\n'
    'support_efforts = ["low", "high", "max"]\n'
    'default_effort = "high"\n'
)
THINKING_TOML = '[thinking]\nenabled = true\neffort = "high"\n'


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
    assert "from provider_prompt import launch" in text
    assert 'launch("kimi", sys.argv[1:])' in text
    assert "subprocess" not in text


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
    agent, skills = owner.kimi_agent_bundle(b"Review the sealed context.", tmp_path)
    assert skills.is_dir() and not tuple(skills.iterdir())
    expected = (
        "---\nname: orchestrarium-bundle-reviewer\n"
        "description: Reviews only the context bundled in this file\n"
        "tools: []\nsubagents: []\n---\n\n"
    )
    text = agent.read_text(encoding="utf-8")
    assert text.startswith(expected)
    assert text == expected + "Review the sealed context."


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


def _write_kimi_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    oauth: str = '{ storage = "file", key = "oauth/kimi-code" }',
    credential: bool = True,
    provider_type: str = "kimi",
    model_value: str = "k3",
    model_metadata: str = K3_METADATA_TOML,
    thinking: str = THINKING_TOML,
) -> tuple[Path, Path]:
    user_home = tmp_path / "user"
    source = user_home / ".kimi-code"
    credentials = source / "credentials"
    credentials.mkdir(parents=True)
    (source / "config.toml").write_text(
        "default_model = \"kimi-code/k3\"\n\n"
        "[providers.\"managed:kimi-code\"]\n"
        f"type = {provider_type!r}\nbase_url = \"https://api.example.invalid\"\n"
        f"oauth = {oauth}\n\n"
        "[models.\"kimi-code/k3\"]\n"
        f"model = {model_value!r}\nprovider = \"managed:kimi-code\"\n"
        f"{model_metadata}{thinking}",
        encoding="utf-8",
    )
    if credential:
        (credentials / "kimi-code.json").write_text(
            '{"access_token":"access-secret","refresh_token":"refresh-secret"}',
            encoding="utf-8",
        )
    monkeypatch.setenv("USERPROFILE", str(user_home))
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    return source, run_dir


def test_kimi_private_home_copies_only_exact_oauth_shape_and_token_needles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    source, run_dir = _write_kimi_home(monkeypatch, tmp_path)

    configuration = owner._kimi_sanitized_runtime_home(run_dir)

    private_home = run_dir / "kimi-code-home"
    copied = private_home / "credentials" / "kimi-code.json"
    parsed = tomllib.loads((private_home / "config.toml").read_text(encoding="utf-8"))
    assert parsed["providers"]["managed:kimi-code"]["oauth"] == {
        "storage": "file", "key": "oauth/kimi-code"
    }
    assert parsed["providers"]["managed:kimi-code"]["type"] == "kimi"
    assert parsed["models"]["kimi-code/k3"]["model"] == "k3"
    assert copied.read_bytes() == (source / "credentials" / "kimi-code.json").read_bytes()
    assert {path.name for path in private_home.iterdir()} == {"config.toml", "credentials"}
    assert configuration.needles == (b"access-secret", b"refresh-secret")
    assert "USERPROFILE" not in configuration.child_environment
    assert configuration.child_environment["KIMI_CODE_HOME"] == str(private_home)
    assert configuration.child_environment["DO_NOT_TRACK"] == "1"


def test_kimi_private_home_preserves_only_complete_allowlisted_k3_and_thinking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    _source, run_dir = _write_kimi_home(
        monkeypatch,
        tmp_path,
        model_metadata=K3_METADATA_TOML + 'unknown_model_sentinel = "must-not-copy"\n',
        thinking=THINKING_TOML + 'unknown_thinking_sentinel = "must-not-copy"\n',
    )

    owner._kimi_sanitized_runtime_home(run_dir)

    generated = tomllib.loads(
        (run_dir / "kimi-code-home" / "config.toml").read_text(encoding="utf-8")
    )
    model = generated["models"]["kimi-code/k3"]
    assert model == {
        "model": "k3",
        "provider": "managed:kimi-code",
        "max_context_size": 1048576,
        "capabilities": [
            "thinking",
            "always_thinking",
            "image_in",
            "video_in",
            "tool_use",
        ],
        "display_name": "K3",
        "support_efforts": ["low", "high", "max"],
        "default_effort": "high",
    }
    assert generated["thinking"] == {"enabled": True, "effort": "high"}
    assert "unknown_model_sentinel" not in model
    assert "unknown_thinking_sentinel" not in generated["thinking"]


@pytest.mark.parametrize(
    "model_metadata,thinking",
    (
        (K3_METADATA_TOML.replace('default_effort = "high"\n', ""), THINKING_TOML),
        (K3_METADATA_TOML.replace("max_context_size = 1048576", 'max_context_size = "bad"'), THINKING_TOML),
        (K3_METADATA_TOML, '[thinking]\nenabled = true\n'),
        (K3_METADATA_TOML, '[thinking]\nenabled = "true"\neffort = "high"\n'),
        (K3_METADATA_TOML, '[thinking]\nenabled = true\neffort = "unsupported"\n'),
    ),
)
def test_kimi_private_home_rejects_missing_or_malformed_required_k3_or_thinking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_metadata: str,
    thinking: str,
) -> None:
    owner = _load_owner()
    _source, run_dir = _write_kimi_home(
        monkeypatch, tmp_path, model_metadata=model_metadata, thinking=thinking
    )

    with pytest.raises(ValueError, match="E_KIMI_AUTH_STORAGE_INVALID"):
        owner._kimi_sanitized_runtime_home(run_dir)

    assert not (run_dir / "kimi-code-home").exists()


def test_kimi_private_home_canonicalizes_case_equivalent_system_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner()
    _source, run_dir = _write_kimi_home(monkeypatch, tmp_path)
    monkeypatch.setattr(
        owner.os,
        "environ",
        {
            "USERPROFILE": str(tmp_path / "user"),
            "SystemRoot": "legacy-system-root",
            "SYSTEMROOT": "canonical-system-root",
            "WINDIR": "windows-directory",
            "COMSPEC": "command-shell",
        },
    )

    configuration = owner._kimi_sanitized_runtime_home(run_dir)

    names = tuple(configuration.child_environment)
    assert len({name.casefold() for name in names}) == len(names)
    assert [name for name in names if name.casefold() == "systemroot"] == ["SYSTEMROOT"]
    assert configuration.child_environment["SYSTEMROOT"] == "canonical-system-root"
    assert configuration.child_environment["WINDIR"] == "windows-directory"
    assert configuration.child_environment["COMSPEC"] == "command-shell"


@pytest.mark.parametrize(
    "oauth,credential",
    (
        ('{ storage = "memory", key = "oauth/kimi-code" }', True),
        ('{ storage = "file", key = "oauth/kimi-code/extra" }', True),
        ('{ storage = "file", key = "oauth/../escape" }', True),
        ('{ storage = "file", key = "oauth/" }', True),
        ('{ storage = "file", key = "oauth/kimi-code" }', False),
    ),
)
def test_kimi_private_home_rejects_unknown_or_unsafe_oauth_storage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, oauth: str, credential: bool
) -> None:
    owner = _load_owner()
    _source, run_dir = _write_kimi_home(
        monkeypatch, tmp_path, oauth=oauth, credential=credential
    )

    with pytest.raises(ValueError, match="E_KIMI_AUTH_STORAGE_INVALID"):
        owner._kimi_sanitized_runtime_home(run_dir)
    assert not (run_dir / "kimi-code-home").exists()


@pytest.mark.parametrize(
    "provider_type,model_value",
    (("other", "k3"), ("kimi", "other")),
)
def test_kimi_private_home_rejects_mismatched_production_model_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, provider_type: str, model_value: str
) -> None:
    owner = _load_owner()
    _source, run_dir = _write_kimi_home(
        monkeypatch, tmp_path, provider_type=provider_type, model_value=model_value
    )

    with pytest.raises(ValueError, match="E_KIMI_AUTH_STORAGE_INVALID"):
        owner._kimi_sanitized_runtime_home(run_dir)


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
