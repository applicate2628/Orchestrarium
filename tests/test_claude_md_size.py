"""Enforce the always-loaded Claude Code entrypoint size and rule manifest.

The real validator is invoked as a subprocess so ``pytest tests/`` exercises the
same command-line contract maintainers use directly.  Exact manifest equality
and per-token destructive copies prove that every declared protection token is
both present and enforced; token presence does not by itself prove normative
force, which remains an independent semantic-review responsibility.
"""

from __future__ import annotations

import hashlib
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "validate-claude-md.py"
CLAUDE_MD = REPO_ROOT / "src.claude" / "CLAUDE.md"
REFERENCE = REPO_ROOT / "references-claude" / "claude-md-structural-enforcement.md"
POST_EXTRACTION_SIZE_CAP = 36_771
NON_BINDING_SIZE_CAP = 1_000_000
BOOTSTRAP_SHA256 = "07374be13bb75fa40e827663927c619540f714b5e04f98a09ffd5b665c957b81"

EXPECTED_PAYLOADS: dict[str, tuple[int, str]] = {
    "structural-overview": (
        1_265,
        "488c41acb051ccf6100422b28b3d4ded846e8d9cdd88fb937fb9b383f8d70319",
    ),
    "hook-behavior-contracts": (
        17_038,
        "5419e8b9c76f10964a3410a1a287b7b3638d07d1ccf727ce5f9e1f7c895923a9",
    ),
    # Payload pins force deliberate review of current hook behavior, placement,
    # and installer truth before a canonical-reference edit can pass.
    "hook-entrypoints-placement": (
        924,
        "98017e791601949a09f1d0ba4e32c7a429195dcdff99cca1b7f0df52a66d45ee",
    ),
    "installer-removal-json-path": (
        5_254,
        "1810bf29901fcf68b0efabc55aacafbd9b5f49aed5da325afb8b79cd7bce27fa",
    ),
}

EXPECTED_MANIFEST: dict[str, tuple[str, ...]] = {
    "install anchors": (
        "@AGENTS.md",
        "## Delegation rule",
        "## Publication safety scan",
    ),
    "bootstrap teeth": (
        "STOP. Universal premise rule first",
        "**(a0) Pre-action orientation trigger**",
        "**(a) Pre-fix trigger**",
        "**(b) Pre-commit trigger**",
        "REPOSITORY ORIENTATION: scope=",
        "**Diagnostic data.**",
        "**Hypothesis inventory.**",
        "ASSUMPTION (UNVERIFIED)",
        "**Scope proportionality.**",
        "Fix means correct logic, not workaround",
        "**Recovery readiness.**",
        "most likely means",
        "while I'm here let me also",
        "I'll just commit this and we can fix it if wrong",
    ),
    "structural-enforcement teeth": (
        "They are backstops; they do not replace the text rules above.",
        "prompts should allow relevant MCP use",
        "gate captures and directly executes the verified",
        "a subagent must never be blocked",
        "This exemption never transfers ownership: the dispatching main conversation still owns diagnostic discipline and publication authorization",
        "Transcript/manual results cannot authorize",
        "Stop hooks do not replace the main conversation's current-turn status checks or work-item close/archive ownership",
        "Reminder hooks re-anchor Model Context Protocol (MCP) discovery/use after compaction, active delegation/recovery, scratch preservation, and every-turn continuity",
        "AUDIT mode",
        "fail-open",
        "[skip-bugfix-discipline]` bypasses the PreToolUse guard for the next turn",
        "[approve-publication]` opens the git-push gate for one turn — honored ONLY when it appears in the user's own last message",
        "[acknowledge-passive-stop]` bypasses one passive-polling Stop decision when the assistant is intentionally handing off to the user",
        "Physical location owns lifecycle membership",
    ),
    "delegation and recovery teeth": (
        "/agents-init-project",
        "externalProvider: auto | codex | claude | gemini | qwen | kimi | grok",
        "Gemini and Qwen are `WEAK MODEL / NOT RECOMMENDED`",
        "never a provider entry inside `externalPriorityProfiles`",
        "Every specialist invocation MUST use the Agent tool",
        "Lead is never spawned as a subagent",
        "The main conversation owns `work-items/`",
        "**Close is mandatory.**",
    ),
    "routing and role teeth": (
        "## Slash command auto-invocation",
        "**Auto-invocation contract:**",
        "**Dispatch index**",
        "## Coexistence with the superpowers plugin",
        "New feature, exploration, or unclear request → invoke `brainstorming` first, then pick a template.",
        "Already in mid-flow with admitted scope",
        "## Role definitions",
        "Pre-publication scan: run `/agents-check-safety`",
    ),
}


def _require_validator() -> None:
    if not VALIDATOR.is_file():
        pytest.skip(f"validator contract is not implemented yet: {VALIDATOR}")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    _require_validator()
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
    )


def _production_manifest() -> dict[str, tuple[str, ...]]:
    _require_validator()
    namespace = runpy.run_path(str(VALIDATOR))
    manifest = namespace.get("MANIFEST")
    assert isinstance(manifest, dict), "validator must expose grouped MANIFEST"
    return {group: tuple(tokens) for group, tokens in manifest.items()}


def _binding_size(path: Path) -> int:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    return max(len(text), len(raw))


def _reference_payload(raw: bytes, payload_id: str) -> bytes:
    begin = f"<!-- BEGIN ORCHESTRARIUM PAYLOAD: {payload_id} -->\n".encode()
    end = f"<!-- END ORCHESTRARIUM PAYLOAD: {payload_id} -->".encode()
    assert raw.count(begin) == 1, f"expected one begin delimiter for {payload_id}"
    assert raw.count(end) == 1, f"expected one end delimiter for {payload_id}"
    start = raw.index(begin) + len(begin)
    finish = raw.index(end, start)
    return raw[start:finish]


def test_validator_script_exists() -> None:
    assert VALIDATOR.is_file(), f"Claude Markdown validator missing: {VALIDATOR}"


def test_live_claude_md_passes_at_post_extraction_cap_and_reports_exact_counts() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr
    for expected in (
            "Code points: 36498",
            "UTF-8 bytes: 36678",
            "Binding size: 36678",
        "Size cap: 36771",
        "Warning threshold: 36521",
        "Manifest: 47/47",
        "RESULT: PASS",
    ):
        assert expected in result.stdout, result.stdout


def test_tiny_size_cap_fails_closed() -> None:
    result = _run("--size-cap", "1000")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAIL: Claude Markdown binding size 36678 > size cap 1000" in result.stdout
    assert "RESULT: FAIL" in result.stdout


@pytest.mark.parametrize(
    "cap_offset",
    (250, 0),
    ids=("binding-equals-warning-threshold", "binding-equals-size-cap"),
)
def test_warning_band_endpoints_are_inclusive_and_non_failing(
    tmp_path: Path, cap_offset: int
) -> None:
    copy = tmp_path / "CLAUDE warning.md"
    copy.write_bytes(CLAUDE_MD.read_bytes())
    binding = _binding_size(copy)
    cap = binding + cap_offset
    threshold = cap - 250

    result = _run("--claude-md", str(copy), "--size-cap", str(cap))

    assert binding in (threshold, cap)
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Warning threshold: {threshold}" in result.stdout
    assert f"WARNING: binding size {binding} is in warning band [{threshold}, {cap}]" in result.stdout
    assert "RESULT: PASS" in result.stdout


def test_over_cap_temporary_content_fails(tmp_path: Path) -> None:
    copy = tmp_path / "CLAUDE over.md"
    copy.write_bytes(CLAUDE_MD.read_bytes())
    binding = _binding_size(copy)

    result = _run("--claude-md", str(copy), "--size-cap", str(binding - 1))

    assert result.returncode == 1, result.stdout + result.stderr
    assert f"FAIL: Claude Markdown binding size {binding} > size cap {binding - 1}" in result.stdout


def test_missing_source_path_fails_closed(tmp_path: Path) -> None:
    missing = tmp_path / "missing" / "CLAUDE.md"
    result = _run("--claude-md", str(missing), "--size-cap", str(NON_BINDING_SIZE_CAP))
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"FAIL: Claude Markdown file not found: {missing}" in result.stdout
    assert "RESULT: FAIL" in result.stdout


def test_invalid_utf8_fails_closed(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid-utf8.md"
    invalid.write_bytes(b"@AGENTS.md\n\xff\n")
    result = _run("--claude-md", str(invalid), "--size-cap", str(NON_BINDING_SIZE_CAP))
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAIL: Claude Markdown is not valid UTF-8:" in result.stdout
    assert "RESULT: FAIL" in result.stdout


def test_manifest_matches_the_complete_lose_nothing_contract() -> None:
    assert _production_manifest() == EXPECTED_MANIFEST


def test_unchanged_copy_passes_and_every_manifest_token_removal_fails(tmp_path: Path) -> None:
    manifest = _production_manifest()
    tokens = [token for group in manifest.values() for token in group]
    assert len(tokens) == 47
    assert len(tokens) == len(set(tokens)), "manifest tokens must be unique"

    source = CLAUDE_MD.read_text(encoding="utf-8", errors="strict")
    unchanged = tmp_path / "unchanged.md"
    unchanged.write_bytes(source.encode("utf-8"))
    unchanged_result = _run(
        "--claude-md", str(unchanged), "--size-cap", str(NON_BINDING_SIZE_CAP)
    )
    assert unchanged_result.returncode == 0, unchanged_result.stdout + unchanged_result.stderr

    for index, token in enumerate(tokens):
        assert token in source, f"live CLAUDE.md lacks manifest token {token!r}"
        tampered = source.replace(token, "")
        assert tampered != source
        candidate = tmp_path / f"missing-token-{index:02d}.md"
        candidate.write_bytes(tampered.encode("utf-8"))

        result = _run(
            "--claude-md", str(candidate), "--size-cap", str(NON_BINDING_SIZE_CAP)
        )

        assert result.returncode == 1, (
            f"removing {token!r} did not fail closed:\n{result.stdout}\n{result.stderr}"
        )
        assert token in result.stdout, (
            f"validator did not name missing token {token!r}:\n{result.stdout}"
        )


def test_bootstrap_lines_are_byte_identical_to_the_accepted_baseline() -> None:
    lines = CLAUDE_MD.read_bytes().splitlines(keepends=True)
    bootstrap = b"".join(lines[6:68])
    assert hashlib.sha256(bootstrap).hexdigest() == BOOTSTRAP_SHA256


def test_reference_payloads_are_hash_pinned_unique_and_absent_from_entrypoint() -> None:
    reference_raw = REFERENCE.read_bytes()
    reference_raw.decode("utf-8", errors="strict")
    source_raw = CLAUDE_MD.read_bytes()
    prior_end = -1

    for payload_id, (expected_bytes, expected_sha256) in EXPECTED_PAYLOADS.items():
        begin = f"<!-- BEGIN ORCHESTRARIUM PAYLOAD: {payload_id} -->\n".encode()
        payload = _reference_payload(reference_raw, payload_id)
        begin_at = reference_raw.index(begin)
        assert begin_at > prior_end, f"payload order changed at {payload_id}"
        prior_end = begin_at + len(begin) + len(payload)
        assert len(payload) == expected_bytes
        assert hashlib.sha256(payload).hexdigest() == expected_sha256
        assert reference_raw.count(payload) == 1
        assert source_raw.count(payload) == 0


def test_required_anchors_and_exact_one_canonical_reference_pointer() -> None:
    text = CLAUDE_MD.read_text(encoding="utf-8", errors="strict")
    pointer = (
        "Full detail: [Claude Markdown structural-enforcement maintainer reference]"
        "(../references-claude/claude-md-structural-enforcement.md)."
    )
    for anchor in ("@AGENTS.md", "## Delegation rule", "## Publication safety scan"):
        assert text.splitlines().count(anchor) == 1
    assert text.splitlines().count(pointer) == 1
    assert text.count("Full detail:") == 1
    assert REFERENCE.is_file()


def test_live_and_created_tracked_text_files_are_lf_only() -> None:
    candidates = (
        CLAUDE_MD,
        Path(__file__),
        VALIDATOR,
        REFERENCE,
        REPO_ROOT / "references-claude" / "README.md",
        REPO_ROOT / "RELEASE_NOTES.md",
    )
    for path in candidates:
        if not path.is_file():
            continue
        raw = path.read_bytes()
        assert b"\r" not in raw, f"tracked text file is not LF-only: {path}"
        raw.decode("utf-8", errors="strict")
