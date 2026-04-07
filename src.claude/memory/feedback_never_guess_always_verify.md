---
name: feedback_never_guess_always_verify
description: Always verify facts before stating them. Never guess, assume, or hallucinate file contents, paths, duplication status, or repo state.
type: feedback
---

**Rule:** Always verify, never guess. Before stating any fact about the codebase — file existence, content, paths, what a file duplicates or doesn't — read the file first. Never assume, infer, or hallucinate.

**Why (1):** Hallucinated that CLAUDE.md was 100% duplicated by .claude/agents/lead.md, deleted important content based on false assumption, and broke the file.

**Why (2):** Invented `~/.claude/skills/` — a directory path that does not exist. The real location is `~/.claude/agents/`. Made up the path instead of reading the filesystem.

**Why (3):** Copied files to `~/.claude/skills/` and `~/.claude/memory/` — neither were real directories, so the copies went to wrong places and the "installed" skills were never actually discoverable.

**How to apply:**

- Before any claim about file state, content overlap, what's duplicated, what's missing, what's stale — use Read/Grep/Bash to verify first.
- Before referencing any path (file, directory, system location) — CHECK it exists before stating it does. Do not invent directory names, config keys, or API endpoints. Always verify first.
- When in doubt, say "let me check" instead of making a definitive statement.
- This applies across ALL projects, not just one repo.