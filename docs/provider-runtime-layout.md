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
| project-local | `<project>/GEMINI.md`, root `<project>/AGENTS.md` when absent, `<project>/.gemini/skills/`, `<project>/.gemini/agents/`, `<project>/.gemini/commands/` |
| global | `~/.gemini/GEMINI.md`, `~/.gemini/AGENTS.md`, `~/.gemini/skills/`, `~/.gemini/agents/`, `~/.gemini/commands/` |

## Notes

- `references-gemini/` and `docs/` stay in the source branch; they are not copied into target projects.
- `.gemini/.agents-mode` is an optional Orchestrarium overlay, not a Gemini-native replacement for `.gemini/settings.json`.
- `GEMINI.md` is still the installed governance entrypoint, and it imports adjacent or project-root `AGENTS.md` through the official Gemini memory-import mechanism.
- `.gemini/agents/` is the installed preview specialist-team layer, while `.gemini/skills/` remains the stable expertise layer.
- MCP servers such as Serena, Fetch, or Context7 remain a `settings.json` or `gemini-extension.json` concern rather than a `GEMINI.md` import concern.
