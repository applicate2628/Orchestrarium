from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER_PATH = ROOT / "scripts" / "provider_prompt.py"
WRAPPER_PATH = ROOT / "scripts" / "invoke-kimi-prompt.py"


def _load_owner():
    spec = importlib.util.spec_from_file_location("kimi_unavailable_owner", OWNER_PATH)
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


def test_kimi_unavailable_before_parse_prompt_probe_or_process(
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

    assert owner.launch("kimi", ["bad", "--unknown"]) == 1
    assert capsys.readouterr().err == "FAIL: E_KIMI_READINESS_UNVERIFIED: provider execution is unavailable\n"


def test_kimi_executor_only_state_is_absent() -> None:
    text = OWNER_PATH.read_text(encoding="utf-8")
    forbidden = (
        "KIMI_BIN",
        "KIMI_PROMPTS_DIR",
        "KIMI_TASK_PROMPT",
        "KIMI_SMOKE_PROMPT",
        "kimi_agent_path",
        "initialize_kimi_agent",
        "resolve_kimi_executable",
        "build_kimi_launch_plan",
        "run_kimi_containment_smoke",
    )
    assert all(token not in text for token in forbidden)
