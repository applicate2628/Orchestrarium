from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_CODEX = ROOT / "scripts" / "install-codex.py"


def _module():
    scripts = str(INSTALL_CODEX.parent)
    inserted = scripts not in sys.path
    if inserted:
        sys.path.insert(0, scripts)
    try:
        spec = importlib.util.spec_from_file_location("install_codex_under_test", INSTALL_CODEX)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if inserted:
            sys.path.remove(scripts)


def test_verify_kimi_compat_flag_maps_to_nonwriting_readiness_diagnostic() -> None:
    module = _module()
    assert module._normalize_compat_args(
        ["--global", "--verify-kimi-enrollment"]
    ) == ["--global", "--enroll-kimi"]
