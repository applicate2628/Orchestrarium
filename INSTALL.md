# Installation

This standalone branch installs the Orchestrarium Claude production pack.

## What Exists Now

| Surface | Status |
|---|---|
| `src.claude/CLAUDE.md` | present |
| `src.claude/agents/` | present |
| `src.claude/commands/` | present |
| `src.claude/skills/` | present |
| `src.claude/agents/scripts/validate-skill-pack.sh` | present |
| `src.claude/agents/scripts/validate-skill-pack.ps1` | present |
| `references-claude/` | present |
| `shared/AGENTS.shared.md` | present |
| `shared/agents-mode.defaults.yaml` | present |
| `scripts/install-claude.*` | present |

## Install Targets

| Mode | Installed surface |
|---|---|
| project-local | `<project>/.claude/CLAUDE.md`, `<project>/.claude/AGENTS.md`, `<project>/.claude/agents/`, `<project>/.claude/commands/`, `<project>/.claude/skills/`, `<project>/.claude/.agents-mode.yaml` |
| global | `~/.claude/CLAUDE.md`, `~/.claude/AGENTS.md`, `~/.claude/agents/`, `~/.claude/commands/`, `~/.claude/skills/`, `~/.claude/.agents-mode.yaml` |

The full monorepo root installer uses Codex plus Claude as the default production install. Pressing Enter selects the default production install there. This standalone Claude branch does not change that production default; it exposes only the explicit Claude installer.

## Commands

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-claude.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\install-claude.ps1 -Global
powershell -ExecutionPolicy Bypass -File .\scripts\install-claude.ps1 -Target D:\my-repo
```

```bash
bash scripts/install-claude.sh
bash scripts/install-claude.sh --global
bash scripts/install-claude.sh --target /path/to/my-repo
```

## Current Usage Model

1. Install the pack into the target project or globally.
2. Run `/agents-init-project` to configure project policies and review or update `.claude/.agents-mode.yaml`.
3. Keep `.claude/.agents-mode.yaml` as the Orchestrarium routing overlay seeded by install.
4. Treat `.claude/CLAUDE.md` as the Claude-native project governance entrypoint and `.claude/AGENTS.md` as the shared-governance import.
5. Keep explicit Claude API or wrapper transport choices in the installed operator overlay or approved wrapper scripts, not in tracked workstation-specific paths.

## Terms and Abbreviations

- `AGENTS.md`: Orchestrarium shared-governance file materialized next to `CLAUDE.md`.
- `API`: Application Programming Interface; a programmatic contract or service surface.
- `CLI`: Command-Line Interface; a terminal command surface.
- `Codex`: OpenAI Codex runtime and production-recommended provider line.
- `Claude Code`: Anthropic Claude runtime and production-recommended provider line.
- `runtime`: installed provider-facing files and directories used by Claude.
- `YAML`: YAML Ain't Markup Language, the configuration format used by `.agents-mode.yaml`.
