# Installation

This standalone Gemini branch now ships a finished Gemini-native installer surface.

## What exists now

| Surface | Status |
|---|---|
| `src.gemini/GEMINI.md` | present |
| `src.gemini/skills/` | present |
| `src.gemini/commands/` | present |
| `src.gemini/extension/` | present |
| `src.gemini/scripts/validate-pack.sh` | present |
| `references-gemini/` | present (repo-local maintainer references) |
| root `install-gemini.*` | present |

## Install targets

| Mode | Installed surface |
|---|---|
| project-local | `<project>/GEMINI.md`, `<project>/.gemini/skills/`, `<project>/.gemini/commands/` |
| global | `~/.gemini/GEMINI.md`, `~/.gemini/skills/`, `~/.gemini/commands/` |

`references-gemini/` is required in the source branch, but it is not copied into target projects or global Gemini homes. It remains a repo-local maintainer reference surface.

## Commands

```powershell
powershell -ExecutionPolicy Bypass -File .\install-gemini.ps1
powershell -ExecutionPolicy Bypass -File .\install-gemini.ps1 -Global
powershell -ExecutionPolicy Bypass -File .\install-gemini.ps1 -Target D:\my-repo
```

```bash
bash install-gemini.sh
bash install-gemini.sh --global
bash install-gemini.sh --target /path/to/my-repo
```

## Current usage model

1. Install the pack into the target project or globally.
2. Use Gemini CLI `/init` in the target project when you want Gemini to create or refresh the user-owned portion of `GEMINI.md`.
3. Treat `src.gemini/` as the source tree for Gemini-specific skills, commands, and future extension packaging.
4. If Orchestrarium shared-routing toggles are needed, use the Gemini `init-project` helper to create `.gemini/.agents-mode` after `/init`.

Important:

- `GEMINI.md` remains owned by Gemini `/init`.
- The installer manages only the `<!-- ORCHESTRARIUM_GEMINI_PACK:... -->` block inside `GEMINI.md`; all content outside that block is preserved on reinstall.
- `.gemini/settings.json` remains Gemini-native runtime config.
- `.gemini/.agents-mode` is an optional Orchestrarium overlay, not a Gemini-native replacement.

## Validation

```bash
bash src.gemini/scripts/validate-pack.sh .
```

## Operator overlay reference

The canonical value-by-value reference for the optional `.gemini/.agents-mode` overlay lives in [docs/agents-mode-reference.md](docs/agents-mode-reference.md). That reference also records task continuity and continue-by-default execution expectations for initialized projects.

The branch-level docs index and runtime-layout map live in [docs/README.md](docs/README.md) and [docs/provider-runtime-layout.md](docs/provider-runtime-layout.md).

The canonical repo-local Gemini governance and methodology references live in [references-gemini/](references-gemini/README.md).
