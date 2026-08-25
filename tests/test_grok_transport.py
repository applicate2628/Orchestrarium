from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER_PATH = ROOT / "scripts" / "provider_prompt.py"
WRAPPER_PATH = ROOT / "scripts" / "invoke-grok-prompt.py"


def _load_owner():
    spec = importlib.util.spec_from_file_location("grok_unavailable_owner", OWNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_grok_wrapper_stays_thin() -> None:
    text = WRAPPER_PATH.read_text(encoding="utf-8")
    assert "from provider_prompt import launch" in text
    assert 'launch("grok", sys.argv[1:])' in text
    assert "subprocess" not in text


def test_grok_unavailable_before_parse_prompt_probe_or_process(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    owner = _load_owner()
    assert not hasattr(owner, "parse_external_control")
    for name in ("prompt_bytes", "resolve_provider_command"):
        monkeypatch.setattr(
            owner, name, lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError(name))
        )
    monkeypatch.setattr(
        owner.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("process")),
    )

    assert owner.launch("grok", ["bad", "--unknown"]) == 1
    assert capsys.readouterr().err == "FAIL: E_GROK_CONTAINMENT_UNAVAILABLE: provider execution is unavailable\n"


def test_grok_executor_only_state_is_absent() -> None:
    text = OWNER_PATH.read_text(encoding="utf-8")
    forbidden = (
        "GROK_BIN",
        "GROK_PROMPTS_DIR",
        "resolve_grok_executable",
        "validate_grok_capability_observation",
        "build_grok_launch_plan",
        "_probe_grok_capabilities",
        "capture_grok_repo_snapshot",
        "assert_grok_repo_immutable",
    )
    assert all(token not in text for token in forbidden)
