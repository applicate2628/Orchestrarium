from __future__ import annotations

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
        "Convert CRLF to LF",
        "trim whitespace only from the end of the entire body",
        "Do not trim individual lines, collapse blank lines, case-fold, or use substring or prefix matching",
        "strictly after the newest exact trigger",
        "current `headRefOid`",
        "`retryable=true`",
        "| failed |",
        "terminal and never `clean` or `in progress`",
    )
    for clause in required_contract:
        assert clause in body, f"missing exact retryable terminal predicate clause: {clause}"

    assert f"```text\n{RETRYABLE_TERMINAL_BODY}\n```" in body
    assert "Generic bot-authored terminal error" not in body


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
