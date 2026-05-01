# Provider Runtime Layouts

This document records the installed runtime layout for the standalone Claude production pack. Claude is part of production `externalProvider: auto` routing together with Codex.

## Quick Comparison

| Provider | Global root | Project root | Production auto-routing |
|---|---|---|---|
| Claude | `~/.claude/` | `<project>/.claude/` | yes, with Codex |

## Claude

### Global

| Item | Path or shape | Notes |
|---|---|---|
| Global context file | `~/.claude/CLAUDE.md` | Claude-native instruction entrypoint managed by the installer block |
| Shared governance copy | `~/.claude/AGENTS.md` | Orchestrarium shared governance materialized from `shared/AGENTS.shared.md` |
| Agent definitions | `~/.claude/agents/` | Claude specialist subagents and contracts |
| Command definitions | `~/.claude/commands/` | Claude slash-command entrypoints |
| Skill payload | `~/.claude/skills/` | Claude skill and workflow helper payload |
| Global operator overlay | `~/.claude/.agents-mode.yaml` | Orchestrarium routing overlay seeded on first global install and preserved on reinstall |

### Local

| Item | Path or shape | Notes |
|---|---|---|
| Project context file | `<project>/.claude/CLAUDE.md` | Claude-native project instruction entrypoint managed by the installer block |
| Shared governance copy | `<project>/.claude/AGENTS.md` | Shared governance imported by `.claude/CLAUDE.md` |
| Agent definitions | `<project>/.claude/agents/` | Project-local Claude specialist subagents and contracts |
| Command definitions | `<project>/.claude/commands/` | Project-local Claude slash commands |
| Skill payload | `<project>/.claude/skills/` | Project-local Claude skill payload |
| Local operator overlay | `<project>/.claude/.agents-mode.yaml` | Orchestrarium routing overlay seeded on first local install and preserved on reinstall |

## Terms and Abbreviations

- `AGENTS.md`: Orchestrarium shared-governance file imported by `CLAUDE.md`.
- `agents-mode`: Orchestrarium routing overlay for provider preferences and execution policy.
- `Claude Code`: Anthropic Claude runtime and provider line.
- `runtime`: installed provider-facing files and directories used by Claude.
- `YAML`: YAML Ain't Markup Language, the configuration format used by `.agents-mode.yaml`.
