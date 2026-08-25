from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER_PATH = ROOT / "scripts" / "provider_prompt.py"
WRAPPER_PATH = ROOT / "scripts" / "invoke-grok-prompt.py"


def _load_owner():
    spec = importlib.util.spec_from_file_location("slice_b_grok_transport", OWNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _observation(live_root: Path) -> dict[str, object]:
    return {
        "signatureStatus": "Valid",
        "signer": "X.AI LLC",
        "version": "grok 1.0.5 (5115b46bc9) [stable]",
        "help": (
            "--prompt-file --output-format json --permission-mode dontAsk "
            "--sandbox read-only --reasoning-effort"
        ),
        "inspectHelp": "inspect --json",
        "models": "logged in with grok.com\n* grok-4.6 (default)",
        "inspectJson": {
            "projectRoot": str(live_root.resolve()),
            "instructionFiles": ["AGENTS.md"],
            "skillRoots": [".agents/skills"],
        },
    }


def test_grok_entry_is_thin_and_process_bound() -> None:
    text = WRAPPER_PATH.read_text(encoding="utf-8")
    assert "from provider_prompt import launch" in text
    assert 'launch("grok", sys.argv[1:])' in text
    assert "subprocess" not in text


def test_grok_exact_path_rejects_path_shim_and_override(tmp_path: Path) -> None:
    owner = _load_owner()
    home = tmp_path / "home"
    exact = home / ".grok" / "bin" / "grok.exe"
    exact.parent.mkdir(parents=True)
    exact.write_bytes(b"official fixture")
    assert owner.resolve_grok_executable(home, {}, lambda _name: str(exact)) == exact

    with pytest.raises(ValueError, match="^E_GROK_PATH_CONFLICT:"):
        owner.resolve_grok_executable(
            home, {"GROK_BIN": str(exact)}, lambda _name: str(exact)
        )
    shim = tmp_path / "npm" / "grok.cmd"
    shim.parent.mkdir()
    shim.write_text("shim", encoding="utf-8")
    with pytest.raises(ValueError, match="^E_GROK_PATH_CONFLICT:"):
        owner.resolve_grok_executable(home, {}, lambda _name: str(shim))


def test_grok_integration_only_returns_before_prompt_capture_and_probe(
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
            "nativeEffort": "high",
            "effortMappingLoss": "none",
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
        owner, "resolve_grok_executable", lambda *_args: (_ for _ in ()).throw(AssertionError("no probe"))
    )
    assert owner.launch(
        "grok",
        ["review", "--prompt-file", str(prompt), "--task-class", "review", "--role", "qa-engineer"],
    ) != 0
    assert "E_GROK_CONTAINMENT_UNAVAILABLE" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("field", "value", "stable_id"),
    (
        ("signatureStatus", "UnknownError", "E_GROK_IDENTITY_INVALID"),
        ("signer", "Other LLC", "E_GROK_IDENTITY_INVALID"),
        ("version", "grok 1.0.5 [preview]", "E_GROK_CAPABILITY_UNAVAILABLE"),
        ("help", "--prompt-file", "E_GROK_CAPABILITY_UNAVAILABLE"),
        ("inspectHelp", "inspect", "E_GROK_CAPABILITY_UNAVAILABLE"),
        ("models", "authentication required", "E_GROK_AUTH_UNREADY"),
        ("models", "logged in\ngrok-3", "E_GROK_MODEL_UNAVAILABLE"),
    ),
)
def test_grok_prelaunch_capability_failures_are_specific(
    tmp_path: Path, field: str, value: str, stable_id: str
) -> None:
    owner = _load_owner()
    live_root = tmp_path / "repo"
    live_root.mkdir()
    observation = _observation(live_root)
    observation[field] = value
    with pytest.raises(ValueError, match=rf"^{stable_id}:"):
        owner.validate_grok_capability_observation(observation, live_root)


def test_grok_capability_fingerprint_has_no_fabricated_shape_or_launch_plan(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    live_root = tmp_path / "repo"
    live_root.mkdir()
    capability = owner.validate_grok_capability_observation(
        _observation(live_root), live_root
    )
    assert len(capability.fingerprint) == 64
    task = tmp_path / "private" / "prompt.md"
    task.parent.mkdir()
    task.write_text("review\n", encoding="utf-8")
    with pytest.raises(ValueError, match="^E_GROK_CONTAINMENT_UNAVAILABLE:"):
        owner.build_grok_launch_plan(
            task_file=task,
            live_root=live_root,
            capability=capability,
            provider_flags=[],
        )


def test_grok_unverified_effort_and_result_shape_fail_pre_spawn(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    live_root = tmp_path / "repo"
    live_root.mkdir()
    capability = owner.validate_grok_capability_observation(
        _observation(live_root), live_root
    )
    task = tmp_path / "prompt.md"
    task.write_text("review\n", encoding="utf-8")
    with pytest.raises(ValueError, match="^E_GROK_EFFORT_UNSUPPORTED:"):
        owner.build_grok_launch_plan(
            task_file=task,
            live_root=live_root,
            capability=capability,
            provider_flags=["--reasoning-effort", "high"],
        )


def test_grok_live_root_discovery_and_immutability() -> None:
    owner = _load_owner()
    before = {
        "status": "",
        "unstagedDiff": "",
        "stagedDiff": "",
        "fixtureInventory": [["fixture.txt", "abc"]],
    }
    owner.assert_grok_repo_immutable(before, dict(before))
    changed = dict(before)
    changed["status"] = "?? mutation.txt"
    with pytest.raises(ValueError, match="^E_GROK_LIVE_REPO_MUTATION:"):
        owner.assert_grok_repo_immutable(before, changed)


def test_grok_requires_high_effort_from_the_accepted_policy(tmp_path: Path) -> None:
    owner = _load_owner()
    accepted = {
        "status": "external-required",
        "requiredEffort": "high",
        "nativeEffort": "high",
        "effortMappingLoss": "none",
        "mutationClass": "read-only",
        "independentVerification": True,
        "finalAuthorizingRole": False,
    }
    assert owner.require_external_realization("grok", accepted) == accepted
    rejected = dict(accepted)
    rejected["requiredEffort"] = "medium"
    with pytest.raises(ValueError, match="^E_GROK_EFFORT_UNSUPPORTED:"):
        owner.require_external_realization("grok", rejected)


def test_grok_caller_shape_flag_is_rejected_without_fabricated_evidence(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    live_root = tmp_path / "repo"
    live_root.mkdir()
    with pytest.raises(ValueError, match="^E_GROK_RESULT_SHAPE_UNVERIFIED:"):
        owner.parse_control(["topic", "--grok-result-shape-file", "caller.json"])


def test_grok_probe_collects_every_required_surface_before_task_spawn(
    tmp_path: Path,
) -> None:
    owner = _load_owner()
    live_root = tmp_path / "repo"
    live_root.mkdir()
    executable = tmp_path / "home" / ".grok" / "bin" / "grok.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"official fixture")
    calls: list[tuple[tuple[str, ...], Path]] = []

    outputs = {
        ("--version",): "grok 1.0.5 (5115b46bc9) [stable]",
        ("--help",): (
            "--prompt-file --output-format json --permission-mode dontAsk "
            "--sandbox read-only --reasoning-effort"
        ),
        ("inspect", "--help"): "inspect --json",
        ("models",): "logged in with grok.com\n* grok-4.6 (default)",
        ("inspect", "--json"): json.dumps(_observation(live_root)["inspectJson"]),
    }

    def runner(argv: list[str], cwd: Path) -> str:
        tail = tuple(argv[1:])
        calls.append((tail, cwd))
        return outputs[tail]

    capability = owner._probe_grok_capabilities(
        executable,
        live_root,
        identity_probe=lambda _path: {
            "signatureStatus": "Valid",
            "signer": "X.AI LLC",
        },
        command_runner=runner,
    )
    assert len(capability.fingerprint) == 64
    assert [tail for tail, _cwd in calls] == list(outputs)
    assert {cwd for _tail, cwd in calls} == {live_root}
