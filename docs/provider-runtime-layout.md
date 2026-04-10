# Claude Runtime Layout

This file is the branch-local runtime-layout reference for the standalone Claude Code pack.

## Source branch surface

| Path | Purpose |
|---|---|
| `docs/` | Branch-local layout and maintainer docs |
| `references-claude/` | Repo-local governance references and diagrams |
| `src.claude/` | Installable Claude Code pack source |
| `install-claude.sh`, `install-claude.ps1` | Installer entrypoints |
| `README.md`, `INSTALL.md` | Maintainer-facing repo manuals |

## Installed surface

| Mode | Installed paths |
|---|---|
| project-local | `<project>/.claude/AGENTS.md`, `<project>/.claude/CLAUDE.md`, `<project>/.claude/agents/`, `<project>/.claude/skills/` |
| global | `~/.claude/AGENTS.md`, `~/.claude/CLAUDE.md`, `~/.claude/agents/`, `~/.claude/skills/` |

## Notes

- `references-claude/` and `docs/` stay in the source branch; they are not copied into target projects.
- Project-local operator state lives in `.claude/.agents-mode`.
- The installed governance entrypoint is `.claude/CLAUDE.md`, which imports `.claude/AGENTS.md`.
