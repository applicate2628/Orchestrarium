"""Cross-provider DP3 candidate-route contract."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / "src.claude" / "agents" / "contracts" / "design-panel.md"
CODEX = ROOT / "src.codex" / "skills" / "design-panel" / "SKILL.md"
MARKER = "DP3-NATIVE-ROUTE-UNVERIFIED"
SESSION_REUSE_ROUTES = (
    "--continue",
    "--resume",
    "--session-id",
    "--fork-session",
    "--from-pr",
    "--teleport",
    "exec resume",
)


def test_candidate_routes_are_external_and_fail_closed_on_both_provider_lines() -> None:
    for path in (CLAUDE, CODEX):
        text = path.read_text(encoding="utf-8")
        assert MARKER in text, path
        assert "$external-worker" in text, path
        assert "file-based prompt" in text, path
        assert "UNVERIFIED" in text, path
        assert "BLOCKED:dependency" in text, path
        assert "never silently reduce quorum" in text, path
        assert "internal fallback" in text, path


def test_candidate_routes_forbid_provider_session_reuse_on_both_provider_lines() -> None:
    for path in (CLAUDE, CODEX):
        text = path.read_text(encoding="utf-8")
        normalized = " ".join(text.split())
        for route in SESSION_REUSE_ROUTES:
            assert route in text, (path, route)
        assert "Inspect the resolved provider argv" in text, path
        assert "never counted toward quorum" in normalized, path


def test_claude_binding_has_no_native_candidate_route() -> None:
    text = CLAUDE.read_text(encoding="utf-8")
    for retired in (
        "| Design lane (internal)",
        "`run_in_background: true`",
        "Same-vendor Agent subagents return",
    ):
        assert retired not in text


def test_codex_binding_has_no_stale_claude_native_fanout_relation() -> None:
    text = CODEX.read_text(encoding="utf-8")
    assert "Claude background-Agent fan-out" not in text
