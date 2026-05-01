# Installation

This standalone branch installs the Orchestrarium Gemini example pack. Gemini remains `WEAK MODEL / NOT RECOMMENDED`; production default routing stays on Codex plus Claude, and explicit Gemini routing is manual example or compatibility use only.

## What Exists Now

| Surface | Status |
|---|---|
| `src.gemini/GEMINI.md` | present |
| `src.gemini/skills/` | present |
| `src.gemini/agents/` | present |
| `src.gemini/commands/` | present |
| `src.gemini/extension/` | present |
| `src.gemini/scripts/validate-pack.sh` | present |
| `src.gemini/scripts/validate-pack.ps1` | present |
| `references-gemini/` | present |
| `shared/AGENTS.shared.md` | present |
| `shared/agents-mode.defaults.yaml` | present |
| `scripts/install-gemini.*` | present |

## Install Targets

| Mode | Installed surface |
|---|---|
| project-local | `<project>/GEMINI.md`, root `<project>/AGENTS.md` when absent, `<project>/.gemini/extensions/orchestrarium-gemini/`, `<project>/.gemini/.agents-mode.yaml` |
| global | `~/.gemini/GEMINI.md`, `~/.gemini/AGENTS.md`, `~/.gemini/extensions/orchestrarium-gemini/`, `~/.gemini/.agents-mode.yaml` |

The full monorepo root installer uses Codex plus Claude as the default production install. Pressing Enter selects the default production install there. This standalone Gemini branch does not change that production default; it exposes only the explicit Gemini example installer.

## Commands

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-gemini.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\install-gemini.ps1 -Global
powershell -ExecutionPolicy Bypass -File .\scripts\install-gemini.ps1 -Target D:\my-repo
```

```bash
bash scripts/install-gemini.sh
bash scripts/install-gemini.sh --global
bash scripts/install-gemini.sh --target /path/to/my-repo
```

## Current Usage Model

1. Install the pack into the target project or globally.
2. Run Gemini `/init` in the target project when you want Gemini to create or refresh the user-owned portion of `GEMINI.md`.
3. Keep `.gemini/settings.json` as the Gemini-native runtime config surface.
4. Keep `.gemini/.agents-mode.yaml` as the Orchestrarium routing overlay seeded by install and reviewed by the Gemini `init-project` helper.
5. Do not treat explicit `externalProvider: gemini` as a production recommendation; it is an example-only route.

## Terms and Abbreviations

- `AGENTS.md`: Orchestrarium shared-governance file materialized next to `GEMINI.md`.
- `Codex`: OpenAI Codex runtime and production-recommended provider line.
- `Claude`: Anthropic Claude runtime and production-recommended provider line.
- `Gemini`: Google Gemini provider line, kept here as an explicit example integration.
- `runtime`: installed provider-facing files and directories used by Gemini.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for Gemini as example-only and excluded from production defaults.
- `YAML`: YAML Ain't Markup Language, the configuration format used by `.agents-mode.yaml`.
