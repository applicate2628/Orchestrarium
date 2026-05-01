# Provider Runtime Layouts

This document records the installed runtime layout for the standalone Codex production pack. Codex is part of production `externalProvider: auto` routing together with Claude.

## Quick Comparison

| Provider | Global root | Project root | Production auto-routing |
|---|---|---|---|
| Codex | `~/.codex/` | `<project>/.agents/` plus `<project>/.codex/` | yes, with Claude |

## Codex

### Global

| Item | Path or shape | Notes |
|---|---|---|
| Global governance file | `~/.codex/AGENTS.md` | Codex-readable governance assembled from `shared/AGENTS.shared.md` and `src.codex/AGENTS.codex.md` |
| Skill payload | `~/.codex/skills/` | Codex skills and workflow helpers |
| Built-in default agent override | `~/.codex/agents/default.toml` | Default built-in agent override seeded when absent |
| Built-in worker agent override | `~/.codex/agents/worker.toml` | Worker built-in agent override seeded when absent |
| Built-in explorer agent override | `~/.codex/agents/explorer.toml` | Explorer built-in agent override seeded when absent |
| Global operator overlay | `~/.codex/.agents-mode.yaml` | Orchestrarium routing overlay seeded on first global install and preserved on reinstall |

### Local

| Item | Path or shape | Notes |
|---|---|---|
| Project governance file | `<project>/AGENTS.md` | Codex-readable project governance managed by the installer block |
| Skill payload | `<project>/.agents/skills/` | Project-local Codex skills and workflow helpers |
| Built-in agent overrides | `<project>/.codex/agents/*.toml` | Project-local default, worker, and explorer overrides seeded when absent |
| Local operator overlay | `<project>/.agents/.agents-mode.yaml` | Orchestrarium routing overlay seeded on first local install and preserved on reinstall |

## Terms and Abbreviations

- `AGENTS.md`: Codex-readable governance file assembled from shared and Codex-specific sources.
- `agents-mode`: Orchestrarium routing overlay for provider preferences and execution policy.
- `Codex`: OpenAI Codex runtime and provider line.
- `runtime`: installed provider-facing files and directories used by Codex.
- `TOML`: Tom's Obvious Minimal Language, the configuration format used by Codex agent override files.
- `YAML`: YAML Ain't Markup Language, the configuration format used by `.agents-mode.yaml`.
