from __future__ import annotations

import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATHS = (
    ROOT / "src.codex/skills/github-pr-review-bot/SKILL.md",
    ROOT / "src.claude/skills/github-pr-review-bot/SKILL.md",
)
RETRYABLE_TERMINAL_BODY = (
    'Codex Review: Something went wrong. Try again later by commenting "@codex review".\n'
    "An unknown error occurred"
)


def test_clean_requires_complete_review_thread_inventory() -> None:
    bodies = [path.read_text(encoding="utf-8") for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    body = bodies[0]
    required_contract = (
        "pageInfo.hasNextPage=false",
        "terminal cursor",
        "unresolved current-head bot-thread IDs and count",
        "summary comments",
        "`gh pr view` review/comment fields",
        "nonauthorizing for `clean`",
        "No clean signal from this workflow authorizes merge or publication",
    )
    for clause in required_contract:
        assert clause in body, f"missing fail-closed clean-oracle clause: {clause}"


def test_clean_review_result_taxonomy_includes_semantic_issue_comments() -> None:
    bodies = [path.read_text(encoding="utf-8") for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    body = bodies[0]
    required_contract = (
        "substantive bot-authored current-head review-result",
        "submitted-review or REST issue-comment surface",
        "issue-comment review-result uses `IssueCommentOrder`",
        "verified bot identity on that surface",
        "explicit and unambiguous final no-findings meaning",
        "reviewed-commit binding",
        "full `headRefOid` or an unambiguous commit prefix",
        "complete collections",
        "no current finding comments",
        "no unresolved current bot threads",
        "Wording, emoji, and boilerplate may vary",
        "must not use an exact body, signature, or phrase allowlist",
        "summary-only issue comment remains nonauthorizing",
    )
    for clause in required_contract:
        assert clause in body, f"missing flexible clean review-result clause: {clause}"

    assert "Didn't find any major issues" not in body


def test_retryable_terminal_failure_uses_the_exact_incident_predicate() -> None:
    bodies = [path.read_text(encoding="utf-8") for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    body = bodies[0]
    required_contract = (
        "Orchestrarium repo-local coordinator convention",
        "not official or guaranteed hosted Codex provider behavior",
        '`user.login == "chatgpt-codex-connector[bot]"`',
        '`user.type == "Bot"`',
        "issue-comment REST predicate",
        "GraphQL display login",
        "Convert Carriage Return followed by Line Feed (CRLF) to Line Feed (LF)",
        "trim whitespace only from the end of the entire body",
        "Do not trim individual lines, collapse blank lines, case-fold, or use substring or prefix matching",
        "`IssueCommentOrder` is greater than the bound exact trigger's order",
        "current `headRefOid`",
        "`retryable=true`",
        "| failed |",
        "terminal and never `clean` or `in progress`",
    )
    for clause in required_contract:
        assert clause in body, f"missing exact retryable terminal predicate clause: {clause}"

    assert f"```text\n{RETRYABLE_TERMINAL_BODY}\n```" in body
    assert "Generic bot-authored terminal error" not in body


def test_uncorrelated_terminal_failure_refuses_overlapping_same_head_runs() -> None:
    bodies = [path.read_text(encoding="utf-8") for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    body = bodies[0]
    required_contract = (
        "Ordering proves only that an issue comment is later",
        "Never bind an uncorrelated terminal comment by selecting the newest trigger",
        "same `(repository, pull request, headRefOid)`",
        "exactly one unresolved exact trigger candidate",
        "Two or more unresolved same-head trigger candidates",
        "do not record `failed`, dismiss a run, mutate a retry lineage, or authorize another trigger",
        "has no trigger or provider run identifier",
        "complete hosted preflight must find no unresolved exact trigger",
    )
    for clause in required_contract:
        assert clause in body, f"missing overlapping-run ambiguity guard: {clause}"


def test_unlisted_error_like_prose_fails_closed_and_failure_record_is_bound() -> None:
    bodies = [path.read_text(encoding="utf-8") for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    body = bodies[0]
    required_contract = (
        "separately exact-listed",
        "`failed` with `retryable=false`",
        "otherwise `indeterminate`",
        "never infer either classification from error-like prose",
        "`headRefOid`",
        "`triggerCommentId`",
        "`triggerCreatedAt`",
        "`terminalCommentId`",
        "`terminalCreatedAt`",
        "`terminalAuthorId`",
        "`terminalAuthorLogin`",
        "`normalizedBodySha256`",
        "`terminalSignatureId`",
        "`retryable`",
        "`retryAttemptCount`",
    )
    for clause in required_contract:
        assert clause in body, f"missing fail-closed terminal record clause: {clause}"


def test_retryable_terminal_failure_allows_one_explicitly_authorized_retry() -> None:
    bodies = [path.read_text(encoding="utf-8") for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    body = bodies[0]
    required_contract = (
        "at most one subsequent retry",
        "explicit user authorization",
        "no automatic retry",
        "one active run",
        "duplicate review thread",
    )
    for clause in required_contract:
        assert clause in body, f"missing bounded retry clause: {clause}"


def test_issue_comment_order_is_repo_local_total_order_for_rest_comments() -> None:
    bodies = [path.read_text(encoding="utf-8") for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    body = bodies[0]
    required_contract = (
        "IssueCommentOrder",
        "IssueCommentOrder = (parsed UTC created_at, numeric stable REST issue-comment ID)",
        "numeric stable REST issue-comment ID",
        "repo-local total-order convention",
        "not a GitHub chronological guarantee",
        "newest exact trigger",
        "post-trigger terminal and finding issue-comment evidence",
        "Malformed, missing, duplicate, or incomplete ordering fields",
        "same-time evidence from different surfaces is incomparable",
        "`indeterminate`",
    )
    for clause in required_contract:
        assert clause in body, f"missing issue-comment ordering clause: {clause}"


def test_retry_creation_success_is_bound_before_lineage_count_increments() -> None:
    bodies = [path.read_text(encoding="utf-8") for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    body = bodies[0]
    required_contract = (
        "retryTransitionState",
        "`not-requested | creating | created | creation-failed | reconciliation-required`",
        "durable authorization reference",
        "successorTriggerCommentId",
        "successorTriggerCreatedAt",
        "successorHeadRefOid",
        "confirmed-success-only",
        "increment `retryAttemptCount` from `0` to `1` only after",
    )
    for clause in required_contract:
        assert clause in body, f"missing retry success-binding clause: {clause}"


def test_retry_creation_failure_and_ambiguity_fail_closed_differently() -> None:
    bodies = [path.read_text(encoding="utf-8") for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    body = bodies[0]
    required_contract = (
        "explicit creation failure",
        "complete hosted refresh proves that no successor trigger exists",
        "`creation-failed`",
        "ambiguous creation outcome",
        "`retryTransitionState=reconciliation-required`",
        "must not create another retry trigger",
        "reconcile the existing attempt",
    )
    for clause in required_contract:
        assert clause in body, f"missing retry failure/ambiguity clause: {clause}"


def test_retry_budget_is_owned_by_the_failed_run_and_its_successor_lineage() -> None:
    bodies = [path.read_text(encoding="utf-8") for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    body = bodies[0]
    required_contract = (
        "one retry lineage",
        "at most one successor trigger",
        "successor inherits `retryAttemptCount=1`",
        "must never authorize another successor",
        "one active run",
    )
    for clause in required_contract:
        assert clause in body, f"missing lineage-owned retry budget clause: {clause}"


def test_protocol_terms_expand_transport_and_normalization_acronyms() -> None:
    bodies = [path.read_text(encoding="utf-8") for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    body = bodies[0]
    required_contract = (
        "**REST** — Representational State Transfer.",
        "**GraphQL** — Graph Query Language.",
        "**CRLF** — Carriage Return followed by Line Feed",
        "**LF** — Line Feed",
        "**SHA-256** — Secure Hash Algorithm 256-bit",
    )
    for clause in required_contract:
        assert clause in body, f"missing glossary expansion: {clause}"


def _canonical_skill_body_sha256(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    lines = content.splitlines(keepends=True)
    body_start = 0
    if lines and lines[0].strip() == b"---":
        for index in range(1, len(lines)):
            if lines[index].strip() == b"---":
                body_start = index + 1
                break
    return hashlib.sha256(b"".join(lines[body_start:])).hexdigest()


def test_provider_bodies_and_validator_pins_match_the_canonical_body() -> None:
    bodies = [path.read_bytes() for path in SKILL_PATHS]

    assert bodies[0] == bodies[1]
    expected = _canonical_skill_body_sha256(SKILL_PATHS[0])
    validator_paths = (
        ROOT / "src.codex/skills/lead/scripts/validate-skill-pack.py",
        ROOT / "src.claude/agents/scripts/validate-skill-pack.py",
    )
    for path in validator_paths:
        text = path.read_text(encoding="utf-8")
        match = re.search(
            r"\('check_common_skill_body_pin',\s*'github-pr-review-bot',\s*'([0-9a-f]{64})'",
            text,
        )
        assert match is not None, f"missing github-pr-review-bot body pin: {path}"
        assert match.group(1) == expected, f"stale github-pr-review-bot body pin: {path}"
