"""Regression coverage for Architecture layering source-owner resolution."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/validate-arch-layering-slices.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("arch_layering_slices", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_claude_architect_layering_slice_resolves_to_universal_body() -> None:
    validator = _load_validator()

    assert validator.claude_path(ROOT, "architect") == (
        ROOT / "src.codex/skills/architect/SKILL.md"
    )
    assert validator.claude_path(ROOT, "backend-engineer") == (
        ROOT / "src.claude/agents/backend-engineer.md"
    )


def test_stamp_writer_emits_unchanged_utf8_lf_payload(tmp_path: Path) -> None:
    validator = _load_validator()
    digest = "a" * 64
    (tmp_path / "scripts").mkdir()

    validator.write_stamp(tmp_path, digest)

    assert (tmp_path / "scripts/arch-layering-slices.stamp").read_bytes() == (
        b"# Review stamp for the inlined architecture-layering role slices.\n"
        b"# SHA-256 of shared/references/architecture-layering-hygiene.md (CRLF-normalized) that the\n"
        b"# inlined slices were last reviewed for fidelity against. Regenerate with:\n"
        b"#   python scripts/validate-arch-layering-slices.py --update-stamp\n"
        b"# ONLY after re-reviewing every role slice against the changed reference.\n"
        + digest.encode("ascii")
        + b"\n"
    )


def test_real_layering_gate_does_not_resolve_deleted_claude_architect_body() -> None:
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert "[design/architect/claude] file missing: " not in result.stdout
    assert "src.claude/skills/architect/SKILL.md" not in result.stdout
