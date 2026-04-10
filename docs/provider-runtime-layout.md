# Gemini Runtime Layout

This file is the branch-local runtime-layout reference for the standalone Gemini pack.

## Source branch surface

| Path | Purpose |
|---|---|
| `docs/` | Branch-local operator and layout docs |
| `references-gemini/` | Repo-local governance references and diagrams |
| `src.gemini/` | Installable Gemini pack source tree |
| `install-gemini.sh`, `install-gemini.ps1` | Installer entrypoints |
| `README.md`, `INSTALL.md` | Maintainer-facing repo manuals |

## Installed surface

| Mode | Installed paths |
|---|---|
| project-local | `<project>/GEMINI.md`, `<project>/AGENTS.shared.md`, `<project>/.gemini/skills/`, `<project>/.gemini/commands/` |
| global | `~/.gemini/GEMINI.md`, `~/.gemini/AGENTS.shared.md`, `~/.gemini/skills/`, `~/.gemini/commands/` |

## Notes

- `references-gemini/` and `docs/` stay in the source branch; they are not copied into target projects.
- `.gemini/.agents-mode` is an optional Orchestrarium overlay, not a Gemini-native replacement for `.gemini/settings.json`.
- `GEMINI.md` is still the installed governance entrypoint, and it imports the adjacent `AGENTS.shared.md` through the official Gemini memory-import mechanism.
- MCP servers such as Serena, Fetch, or Context7 remain a `settings.json` or `gemini-extension.json` concern rather than a `GEMINI.md` import concern.
