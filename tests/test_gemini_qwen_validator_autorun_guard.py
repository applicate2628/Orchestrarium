"""Narrow static guard for the retained Gemini/Qwen PowerShell validators."""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATORS = (
    ROOT / "src.gemini/scripts/validate-pack.ps1",
    ROOT / "src.qwen/scripts/validate-pack.ps1",
)

_EAP_STOP = re.compile(
    r"\$ErrorActionPreference\s*=\s*['\"]Stop['\"]"
)
_EAP_RELAX = re.compile(
    r"\$ErrorActionPreference\s*=\s*"
    r"['\"](Continue|SilentlyContinue|Ignore)['\"]"
)


def find_vulnerable_native_calls(
    text: str,
    *,
    window: int = 15,
) -> list[int]:
    """Find native ``2>$null`` calls under unrelaxed file-scoped Stop."""
    lines = text.splitlines()
    if not _EAP_STOP.search(text):
        return []
    hits: list[int] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") or "2>$null" not in line:
            continue
        if "$ErrorActionPreference" in line:
            continue
        preceding = "\n".join(lines[max(0, index - window) : index])
        if _EAP_RELAX.search(preceding):
            continue
        hits.append(index + 1)
    return hits


def test_retained_validators_have_no_autorun_hazard_with_nonvacuous_controls(
) -> None:
    planted_vulnerable = (
        "$ErrorActionPreference = 'Stop'\n"
        "$out = & $git rev-parse --show-toplevel 2>$null\n"
    )
    safe_relaxed = (
        "$ErrorActionPreference = 'Stop'\n"
        "$saved = $ErrorActionPreference\n"
        "$ErrorActionPreference = 'SilentlyContinue'\n"
        "$out = & $git rev-parse --show-toplevel 2>$null\n"
        "$ErrorActionPreference = $saved\n"
    )
    assert find_vulnerable_native_calls(planted_vulnerable) == [2]
    assert find_vulnerable_native_calls(safe_relaxed) == []

    hits: dict[str, list[int]] = {}
    for validator in VALIDATORS:
        assert validator.is_file()
        found = find_vulnerable_native_calls(
            validator.read_text(encoding="utf-8")
        )
        if found:
            hits[str(validator.relative_to(ROOT))] = found
    assert hits == {}
