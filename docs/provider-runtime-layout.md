# Codex Runtime Layout

This file is the branch-local runtime-layout reference for the standalone Codex pack.

## Source branch surface

| Path | Purpose |
|---|---|
| `docs/` | Branch-local operator and layout docs |
| `references-codex/` | Repo-local governance references and diagrams |
| `src.codex/` | Installable Codex pack source |
| `install-codex.sh`, `install-codex.ps1` | Installer entrypoints |
| `README.md`, `INSTALL.md` | Maintainer-facing repo manuals |

## Installed surface

| Mode | Installed paths |
|---|---|
| project-local | `<project>/AGENTS.md`, `<project>/.agents/skills/` |
| global | `~/.codex/AGENTS.md`, `~/.codex/skills/` |

## Notes

- `references-codex/` and `docs/` stay in the source branch; they are not copied into target projects.
- Project-local operator state lives in `.agents/.agents-mode`.
- The installed governance entrypoint is the project root `AGENTS.md`.
