# Provider Runtime Layouts

This document records the installed runtime layout for the standalone Gemini example pack. Gemini is classified as `WEAK MODEL / NOT RECOMMENDED`; production `externalProvider: auto` routing stays on `codex | claude`.

## Quick Comparison

| Provider | Global root | Project root | Production auto-routing |
|---|---|---|---|
| Gemini | `~/.gemini/` | `<project>/.gemini/` | no, explicit example-only route |

## Gemini

### Global

| Item | Path or shape | Notes |
|---|---|---|
| Global context file | `~/.gemini/GEMINI.md` | Gemini-native instruction entrypoint managed by the installer block |
| Shared governance copy | `~/.gemini/AGENTS.md` | Orchestrarium shared governance materialized from `shared/AGENTS.shared.md` |
| Extension package | `~/.gemini/extensions/orchestrarium-gemini/` | Gemini extension payload for skills, agents, commands, and manifest |
| Global operator overlay | `~/.gemini/.agents-mode.yaml` | Orchestrarium routing overlay seeded on first global install and preserved on reinstall |
| Native runtime config | `~/.gemini/settings.json` | Gemini-native runtime config surface; Orchestrarium does not replace it |

### Local

| Item | Path or shape | Notes |
|---|---|---|
| Project context file | `<project>/GEMINI.md` | Gemini-native project instruction entrypoint managed by the installer block |
| Shared governance copy | `<project>/AGENTS.md` | Orchestrarium shared governance materialized when absent or within the managed block |
| Extension package | `<project>/.gemini/extensions/orchestrarium-gemini/` | Project-local Gemini extension payload |
| Local operator overlay | `<project>/.gemini/.agents-mode.yaml` | Orchestrarium routing overlay seeded on first local install and preserved on reinstall |
| Native runtime config | `<project>/.gemini/settings.json` | Gemini-native runtime config surface |

## Terms and Abbreviations

- `AGENTS.md`: Orchestrarium shared-governance file materialized next to `GEMINI.md`.
- `agents-mode`: Orchestrarium routing overlay for provider preferences and execution policy.
- `Gemini`: Google Gemini provider line, kept here as an explicit example integration.
- `runtime`: installed provider-facing files and directories used by Gemini.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for Gemini as example-only and excluded from production defaults.
- `YAML`: YAML Ain't Markup Language, the configuration format used by `.agents-mode.yaml`.
