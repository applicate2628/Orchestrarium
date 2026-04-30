---
name: feedback_never_guess_always_verify
description: Always verify facts before stating them. Never guess, assume, or hallucinate file contents, paths, duplication status, or repo state.
type: feedback
---

**Rule:** Always verify, never guess. Before stating any fact about the codebase — file existence, content, paths, what a file duplicates or doesn't — read the file first. Before claiming a root cause, proposing a fix, or changing behavior for a bug/runtime failure, capture concrete observable data and verify that it rules out plausible alternatives. Never assume, infer, or hallucinate.

**Why (1):** Hallucinated that CLAUDE.md was 100% duplicated by .claude/agents/lead.md, deleted important content based on false assumption, and broke the file.

**Why (2):** Invented `~/.claude/skills/` — a directory path that does not exist. The real location is `~/.claude/agents/`. Made up the path instead of reading the filesystem.

**Why (3):** Copied files to `~/.claude/skills/` and `~/.claude/memory/` — neither were real directories, so the copies went to wrong places and the "installed" skills were never actually discoverable.

**How to apply:**

- Before any claim about file state, content overlap, what's duplicated, what's missing, what's stale — use Read/Grep/Bash to verify first.
- Before referencing any path (file, directory, system location) — CHECK it exists before stating it does. Do not invent directory names, config keys, or API endpoints. Always verify first.
- Before saying "the bug is X" or shipping a fix, capture at least one specific data point such as a log line, return code, field dump, screenshot fact, command output, or reproduction result. If the data does not distinguish the proposed cause from plausible alternatives, add diagnostics or collect the missing datum before iterating.
- When in doubt, say "let me check" instead of making a definitive statement.
- This applies across ALL projects, not just one repo.

## Terms and Abbreviations

- `API`: Application Programming Interface; a programmatic contract exposed by code, a service, or a tool.
- `Bash`: a command-line shell used here as the Claude tool surface for running verification commands.
- `data point`: one concrete observed value, log line, field, return code, screenshot fact, or command result used as evidence.
- `root cause`: the underlying verified cause of a failure, not a guess that merely sounds plausible.
