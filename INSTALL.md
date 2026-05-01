# Installation

This standalone branch installs the Orchestrarium Codex production pack.

## What Exists Now

| Surface | Status |
|---|---|
| `src.codex/AGENTS.codex.md` | present |
| `src.codex/agents/` | present |
| `src.codex/skills/` | present |
| `src.codex/skills/lead/scripts/validate-skill-pack.sh` | present |
| `src.codex/skills/lead/scripts/validate-skill-pack.ps1` | present |
| `references-codex/` | present |
| `shared/AGENTS.shared.md` | present |
| `shared/agents-mode.defaults.yaml` | present |
| `scripts/install-codex.*` | present |

## Install Targets

| Mode | Installed surface |
|---|---|
| project-local | `<project>/AGENTS.md`, `<project>/.agents/skills/`, `<project>/.agents/.agents-mode.yaml`, `<project>/.codex/agents/default.toml`, `<project>/.codex/agents/worker.toml`, `<project>/.codex/agents/explorer.toml` |
| global | `~/.codex/AGENTS.md`, `~/.codex/skills/`, `~/.codex/.agents-mode.yaml`, `~/.codex/agents/default.toml`, `~/.codex/agents/worker.toml`, `~/.codex/agents/explorer.toml` |

The full monorepo root installer uses Codex plus Claude as the default production install. Pressing Enter selects the default production install there. This standalone Codex branch does not change that production default; it exposes only the explicit Codex installer.

## Commands

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-codex.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\install-codex.ps1 -Global
powershell -ExecutionPolicy Bypass -File .\scripts\install-codex.ps1 -Target D:\my-repo
```

```bash
bash scripts/install-codex.sh
bash scripts/install-codex.sh --global
bash scripts/install-codex.sh --target /path/to/my-repo
```

## Current Usage Model

1. Install the pack into the target project or globally.
2. Run `$init-project` to configure project policies and review or update `.agents/.agents-mode.yaml`.
3. Keep `.agents/.agents-mode.yaml` as the Orchestrarium routing overlay seeded by install.
4. Keep Codex built-in agent override payloads in `.codex/agents/` for project installs or `~/.codex/agents/` for global installs.
5. Treat `shared/AGENTS.shared.md` and `src.codex/AGENTS.codex.md` as the source pair that installers merge into installed `AGENTS.md`.

## Terms and Abbreviations

- `AGENTS.md`: Codex-readable governance file assembled from shared and Codex-specific sources.
- `CLI`: Command-Line Interface; a terminal command surface.
- `Codex`: OpenAI Codex runtime and production-recommended provider line.
- `Claude`: Anthropic Claude runtime and production-recommended provider line.
- `runtime`: installed provider-facing files and directories used by Codex.
- `TOML`: Tom's Obvious Minimal Language, the configuration format used by Codex agent override files.
- `YAML`: YAML Ain't Markup Language, the configuration format used by `.agents-mode.yaml`.
