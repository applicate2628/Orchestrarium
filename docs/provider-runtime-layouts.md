# Provider Runtime Layouts

This document records the installed runtime layout for the standalone Qwen example pack. Qwen is classified as `WEAK MODEL / NOT RECOMMENDED`; production `externalProvider: auto` routing stays on `codex | claude`.

## Quick Comparison

| Provider | Global root | Project root | Production auto-routing |
|---|---|---|---|
| Qwen | `~/.qwen/` | `<project>/.qwen/` | no, explicit example-only route |

## Qwen

### Global

| Item | Path or shape | Notes |
|---|---|---|
| Global context file | `~/.qwen/QWEN.md` | Qwen-native instruction entrypoint managed by the installer block |
| Shared governance copy | `~/.qwen/AGENTS.md` | Orchestrarium shared governance materialized from `shared/AGENTS.shared.md` |
| Extension package | `~/.qwen/extensions/orchestrarium-qwen/` | Qwen extension payload for skills, agents, commands, and manifest |
| Global operator overlay | `~/.qwen/.agents-mode.yaml` | Orchestrarium routing overlay seeded on first global install and preserved on reinstall |
| Native runtime config | `~/.qwen/settings.json` | Qwen-native runtime config surface; Orchestrarium does not replace it |

### Local

| Item | Path or shape | Notes |
|---|---|---|
| Project context file | `<project>/QWEN.md` | Qwen-native project instruction entrypoint managed by the installer block |
| Shared governance copy | `<project>/AGENTS.md` | Orchestrarium shared governance materialized when absent or within the managed block |
| Extension package | `<project>/.qwen/extensions/orchestrarium-qwen/` | Project-local Qwen extension payload |
| Local operator overlay | `<project>/.qwen/.agents-mode.yaml` | Orchestrarium routing overlay seeded on first local install and preserved on reinstall |
| Native runtime config | `<project>/.qwen/settings.json` | Qwen-native runtime config surface |

## Terms and Abbreviations

- `AGENTS.md`: Orchestrarium shared-governance file materialized next to `QWEN.md`.
- `agents-mode`: Orchestrarium routing overlay for provider preferences and execution policy.
- `Qwen`: Qwen provider line, kept here as an explicit example integration.
- `runtime`: installed provider-facing files and directories used by Qwen.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for Qwen as example-only and excluded from production defaults.
- `YAML`: YAML Ain't Markup Language, the configuration format used by `.agents-mode.yaml`.
