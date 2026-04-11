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
| project-local | `<project>/GEMINI.md`, root `<project>/AGENTS.md` when absent, `<project>/.gemini/extensions/orchestrarium-gemini/`, `<project>/.gemini/.agents-mode` |
| global | `~/.gemini/GEMINI.md`, `~/.gemini/AGENTS.md`, `~/.gemini/extensions/orchestrarium-gemini/`, `~/.gemini/.agents-mode` |

## Notes

- `references-gemini/` and `docs/` stay in the source branch; they are not copied into target projects.
- `.gemini/.agents-mode` is the Orchestrarium overlay seeded by install, not a Gemini-native replacement for `.gemini/settings.json`. It carries the named priority profiles and per-lane opinion counts used by the Gemini-line external routing story.
- `GEMINI.md` is still the installed governance entrypoint, and it imports adjacent or project-root `AGENTS.md` through the official Gemini memory-import mechanism.
- `.gemini/extensions/orchestrarium-gemini/` is the installed official Gemini extension package that mirrors the current Orchestrarium Gemini payload and owns the installed `gemini-extension.json`.
- Top-level `.gemini/skills/`, `.gemini/agents/`, and `.gemini/commands/` stay open for deliberate user overrides; Orchestrarium does not mirror the same pack into those higher-precedence tiers.
- Reinstall cleans legacy Orchestrarium-owned duplicates from those top-level tiers so extension content does not trigger conflict warnings.
- MCP servers such as Serena, Fetch, or Context7 remain a `settings.json` or installed `gemini-extension.json` concern rather than a `GEMINI.md` import concern.
