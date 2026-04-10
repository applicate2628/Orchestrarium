# Gemini Runtime Layout

This file is the branch-local runtime-layout reference for the standalone Gemini pack.

## Source branch surface

| Path | Purpose |
|---|---|
| `docs/` | Branch-local operator and layout docs |
| `references-gemini/` | Repo-local governance references and diagrams |
| `src.gemini/` | Installable Gemini scaffold source |
| `install-gemini.sh`, `install-gemini.ps1` | Installer entrypoints |
| `README.md`, `INSTALL.md` | Maintainer-facing repo manuals |

## Installed surface

| Mode | Installed paths |
|---|---|
| project-local | `<project>/GEMINI.md`, `<project>/.gemini/skills/`, `<project>/.gemini/commands/` |
| global | `~/.gemini/GEMINI.md`, `~/.gemini/skills/`, `~/.gemini/commands/` |

## Notes

- `references-gemini/` and `docs/` stay in the source branch; they are not copied into target projects.
- `.gemini/.agents-mode` is an optional Orchestrarium overlay, not a Gemini-native replacement for `.gemini/settings.json`.
- The installed governance entrypoint is `GEMINI.md`, with Orchestrarium managing only its pack block.
