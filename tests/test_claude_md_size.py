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
AGENTS_MD = REPO_ROOT / "shared" / "AGENTS.shared.md"
REFERENCE = REPO_ROOT / "references-claude" / "claude-md-structural-enforcement.md"
CLAUDE_DELTA_SIZE_CAP = 8_192
NON_BINDING_SIZE_CAP = 1_000_000

EXPECTED_PAYLOADS: dict[str, tuple[int, str]] = {
    "structural-overview": (
        1_265,
        "488c41acb051ccf6100422b28b3d4ded846e8d9cdd88fb937fb9b383f8d70319",
    ),
    "hook-behavior-contracts": (
        17_997,
        "6a04609faa133108c92c5906e5419db87450b6f6b6fb27e2f8ea7c8efcff6e0c",
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

EXPECTED_SHARED_MANIFEST: dict[str, tuple[str, ...]] = {
    "shared owners": (
        "# Shared Governance",
        "## Role index",
        "## Common skills",
        "### Physical lifecycle V1",
        "### Session persistence rule (mandatory)",
        "## Core delegation principles",
        "## Engineering hygiene",
        "## Publication safety",
    ),
    "shared gates": (
        "`quick-fix`: target+steps",
        "before QA across phases/specialists, assign one integration owner",
        "**Repository orientation; Mechanism inventory before new paths:**",
        "REPOSITORY ORIENTATION: scope=<repo-relative path>; status=<live|mutable|frozen|archived|deprecated|superseded|conflict>; workflow=<repo-relative entry point(s)>; protected=<repo-relative path(s)|none>; evidence=<path:line[,path:line...]>",
        "**Hypothesis disclosure discipline:**",
        "**Pre-fix diagnostic gate:**",
        "**Evidence-based completion:**",
        "Human review before",
    ),
}

EXPECTED_CLAUDE_MANIFEST: dict[str, tuple[str, ...]] = {
    "Claude tool mapping": (
        "## Claude tool mapping",
        "`Bash|PowerShell`",
        "`Edit|Write|NotebookEdit`",
        "commits apply all shared checkpoints",
    ),
    "Claude hooks": (
        "auto-installs thirteen `settings.json` entries",
        "nine structural hooks",
        "They are backstops; they do not replace `AGENTS.md`",
        "a subagent must never be blocked",
        "The first other valid root final receives one reconciliation pass",
        "`stop_hook_active` allows the next Stop",
        "[skip-bugfix-discipline]",
        "[approve-publication]",
        "[approve-mcp-fallback:v1]",
        "[acknowledge-passive-stop]",
    ),
    "Claude delegation": (
        "/agents-init-project",
        "externalProvider: auto | codex | claude | kimi | grok",
        "Every specialist invocation uses the Agent tool",
        "matching `subagent_type`",
        "curated inline role-skills",
        "Lead is never spawned as a subagent",
        "requiresLead",
        "general-purpose",
        "approved thin wrapper",
        "independently verified and nonauthorizing",
        "Grok remains unavailable",
    ),
    "Claude commands and roles": (
        "## Slash command routing",
        ".claude/agents/team-templates/",
        ".claude/commands/agents-help.md",
        "Each command file owns its `## When to auto-invoke` rules",
        "## Role definitions",
        "initialPrompt: /lead",
        "Evaluate the shared `quick-fix` predicate before invoking a process skill",
        "process skills govern method; Orchestrarium governs delegation",
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


def _production_manifests() -> tuple[
    dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]
]:
    _require_validator()
    namespace = runpy.run_path(str(VALIDATOR))
    shared = namespace.get("SHARED_MANIFEST")
    claude = namespace.get("CLAUDE_MANIFEST")
    assert isinstance(shared, dict), "validator must expose grouped SHARED_MANIFEST"
    assert isinstance(claude, dict), "validator must expose grouped CLAUDE_MANIFEST"
    return (
        {group: tuple(tokens) for group, tokens in shared.items()},
        {group: tuple(tokens) for group, tokens in claude.items()},
    )


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


def test_live_composed_entrypoint_passes_with_separate_claude_delta_budget() -> None:
    result = _run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Claude delta size cap: {CLAUDE_DELTA_SIZE_CAP}" in result.stdout
    assert "Shared manifest:" in result.stdout
    assert "Claude manifest:" in result.stdout
    assert "RESULT: PASS" in result.stdout
    assert _binding_size(CLAUDE_MD) <= CLAUDE_DELTA_SIZE_CAP


def test_tiny_size_cap_fails_closed() -> None:
    result = _run("--size-cap", "1000")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "FAIL: Claude delta binding size" in result.stdout
    assert "> size cap 1000" in result.stdout
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
    assert f"FAIL: Claude delta binding size {binding} > size cap {binding - 1}" in result.stdout


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


def test_manifests_match_the_composed_owner_contract() -> None:
    assert _production_manifests() == (
        EXPECTED_SHARED_MANIFEST,
        EXPECTED_CLAUDE_MANIFEST,
    )


def test_unchanged_pair_passes_and_each_owner_fails_on_semantic_removal(
    tmp_path: Path,
) -> None:
    shared_manifest, claude_manifest = _production_manifests()
    shared_source = AGENTS_MD.read_text(encoding="utf-8", errors="strict")
    claude_source = CLAUDE_MD.read_text(encoding="utf-8", errors="strict")
    shared_copy = tmp_path / "AGENTS.md"
    claude_copy = tmp_path / "CLAUDE.md"
    shared_copy.write_text(shared_source, encoding="utf-8")
    claude_copy.write_text(claude_source, encoding="utf-8")
    unchanged_result = _run(
        "--claude-md",
        str(claude_copy),
        "--agents-md",
        str(shared_copy),
        "--size-cap",
        str(NON_BINDING_SIZE_CAP),
    )
    assert unchanged_result.returncode == 0, unchanged_result.stdout + unchanged_result.stderr

    for owner, manifest, source in (
        ("shared", shared_manifest, shared_source),
        ("claude", claude_manifest, claude_source),
    ):
        tokens = [token for group in manifest.values() for token in group]
        assert len(tokens) == len(set(tokens)), f"{owner} manifest tokens must be unique"
        for index, token in enumerate(tokens):
            assert token in source, f"live {owner} owner lacks manifest token {token!r}"
            shared_copy.write_text(shared_source, encoding="utf-8")
            claude_copy.write_text(claude_source, encoding="utf-8")
            candidate = shared_copy if owner == "shared" else claude_copy
            candidate.write_text(source.replace(token, ""), encoding="utf-8")
            result = _run(
                "--claude-md",
                str(claude_copy),
                "--agents-md",
                str(shared_copy),
                "--size-cap",
                str(NON_BINDING_SIZE_CAP),
            )
            assert result.returncode == 1, (
                f"removing {owner} token {token!r} did not fail closed:\n"
                f"{result.stdout}\n{result.stderr}"
            )
            assert token in result.stdout


def test_import_and_duplicate_common_owners_fail_closed(tmp_path: Path) -> None:
    shared_copy = tmp_path / "AGENTS.md"
    claude_copy = tmp_path / "CLAUDE.md"
    shared_copy.write_bytes(AGENTS_MD.read_bytes())
    source = CLAUDE_MD.read_text(encoding="utf-8")
    mutations = (
        source.replace("@AGENTS.md", "", 1),
        source + "\n@AGENTS.md\n",
        source + "\n## Common skills\n\nDuplicated list.\n",
        source + "\n## Bootstrap — duplicated shared rules\n",
    )
    for index, mutation in enumerate(mutations):
        claude_copy.write_text(mutation, encoding="utf-8")
        result = _run(
            "--claude-md",
            str(claude_copy),
            "--agents-md",
            str(shared_copy),
            "--size-cap",
            str(NON_BINDING_SIZE_CAP),
        )
        assert result.returncode == 1, f"mutation {index} passed:\n{result.stdout}"


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


def test_required_anchors_have_no_uninstalled_reference_dependency() -> None:
    text = CLAUDE_MD.read_text(encoding="utf-8", errors="strict")
    for anchor in ("@AGENTS.md", "## Delegation rule", "## Publication safety scan"):
        assert text.splitlines().count(anchor) == 1
    assert "references-claude/" not in text
    assert REFERENCE.is_file()


def test_stop_behavior_stays_the_accepted_concise_62_word_delta() -> None:
    lines = CLAUDE_MD.read_text(encoding="utf-8").splitlines()
    stop_lines = [line for line in lines if line.startswith("- **Stop ownership.**")]
    assert len(stop_lines) == 1
    stop = stop_lines[0]
    assert len(stop.split()) == 62
    for required in (
        "Passive verdicts remain unchanged.",
        "The first other valid root final receives one reconciliation pass",
        "`stop_hook_active` allows the next Stop",
        "even for a standalone answer or pause",
        "cannot guarantee model obedience",
    ):
        assert required in stop


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
