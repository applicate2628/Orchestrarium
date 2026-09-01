from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATHS = (
    ROOT / "src.codex/skills/github-pr-review-bot/SKILL.md",
    ROOT / "src.claude/skills/github-pr-review-bot/SKILL.md",
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
