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
| project-local | `<project>/AGENTS.md`, `<project>/.agents/skills/`, `<project>/.agents/.agents-mode`, `<project>/.codex/agents/` |
| global | `~/.codex/AGENTS.md`, `~/.codex/skills/`, `~/.codex/.agents-mode`, `~/.codex/agents/` |

## Notes

- `references-codex/` and `docs/` stay in the source branch; they are not copied into target projects.
- Installs seed the operator file into the active target: `.agents/.agents-mode` for project installs and `~/.codex/.agents-mode` for global installs.
- Installs also seed Codex built-in custom-agent overrides into `.codex/agents/` for project installs and `~/.codex/agents/` for global installs; the shipped `default`, `worker`, and `explorer` overrides pin those built-ins to `gpt-5.4` with `xhigh`.
- The installed governance entrypoint is the project root `AGENTS.md`.
