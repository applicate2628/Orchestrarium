# Installation

This standalone branch installs the Orchestrarium Qwen example pack. Qwen remains `WEAK MODEL / NOT RECOMMENDED`; production default routing stays on Codex plus Claude, and explicit Qwen routing is manual example or compatibility use only.

## What Exists Now

| Surface | Status |
|---|---|
| `src.qwen/QWEN.md` | present |
| `src.qwen/skills/` | present |
| `src.qwen/agents/` | present |
| `src.qwen/commands/` | present |
| `src.qwen/extension/` | present |
| `src.qwen/scripts/validate-pack.sh` | present |
| `src.qwen/scripts/validate-pack.ps1` | present |
| `references-qwen/` | present |
| `shared/AGENTS.shared.md` | present |
| `shared/agents-mode.defaults.yaml` | present |
| `scripts/install-qwen.*` | present |

## Install Targets

| Mode | Installed surface |
|---|---|
| project-local | `<project>/QWEN.md`, root `<project>/AGENTS.md` when absent, `<project>/.qwen/extensions/orchestrarium-qwen/`, `<project>/.qwen/.agents-mode.yaml` |
| global | `~/.qwen/QWEN.md`, `~/.qwen/AGENTS.md`, `~/.qwen/extensions/orchestrarium-qwen/`, `~/.qwen/.agents-mode.yaml` |

The full monorepo root installer uses Codex plus Claude as the default production install. Pressing Enter selects the default production install there. This standalone Qwen branch does not change that production default; it exposes only the explicit Qwen example installer.

## Commands

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-qwen.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\install-qwen.ps1 -Global
powershell -ExecutionPolicy Bypass -File .\scripts\install-qwen.ps1 -Target D:\my-repo
```

```bash
bash scripts/install-qwen.sh
bash scripts/install-qwen.sh --global
bash scripts/install-qwen.sh --target /path/to/my-repo
```

## Current Usage Model

1. Install the pack into the target project or globally.
2. Run Qwen `/init` in the target project when you want Qwen to create or refresh the user-owned portion of `QWEN.md`.
3. Keep `.qwen/settings.json` as the Qwen-native runtime config surface.
4. Keep `.qwen/.agents-mode.yaml` as the Orchestrarium routing overlay seeded by install and reviewed by the Qwen `init-project` helper.
5. Do not treat explicit `externalProvider: qwen` as production recommendation; it is an example-only route.

## Terms and Abbreviations

- `AGENTS.md`: Orchestrarium shared-governance file materialized next to `QWEN.md`.
- `Codex`: OpenAI Codex runtime and production-recommended provider line.
- `Claude`: Anthropic Claude runtime and production-recommended provider line.
- `Qwen`: Qwen provider line, kept here as an explicit example integration.
- `runtime`: installed provider-facing files and directories used by Qwen.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for Qwen as example-only and excluded from production defaults.
- `YAML`: YAML Ain't Markup Language, the configuration format used by `.agents-mode.yaml`.
