---
name: feedback_never_guess_always_verify
description: Always verify facts before stating them. Never guess, assume, or hallucinate file contents, paths, duplication status, or repo state.
type: feedback
---

**Rule:** Always verify, never guess. Before stating any fact about the codebase — file existence, content, paths, what a file duplicates or doesn't — read the file first. Never assume, infer, or hallucinate.

**Why:** Hallucinated that CLAUDE.md was 100% duplicated by agents/lead.md, deleted important content based on false assumption, and broke the file. Cost was significant rework and trust damage.

**How to apply:** Before any claim about file state, content overlap, what's duplicated, what's missing, what's stale — use Read/Grep/Bash to verify. When in doubt, say "let me check" instead of making a definitive statement. This applies across ALL projects, not just one repo.