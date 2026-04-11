# Installation

This standalone Gemini branch now ships a finished Gemini-native installer surface.

## What exists now

| Surface | Status |
|---|---|
| `src.gemini/GEMINI.md` | present |
| `src.gemini/AGENTS.shared.md` | present |
| `src.gemini/skills/` | present |
| `src.gemini/agents/` | present |
| `src.gemini/commands/` | present |
| `src.gemini/extension/` | present |
| `src.gemini/scripts/validate-pack.sh` | present |
| `src.gemini/scripts/validate-pack.ps1` | present |
| `references-gemini/` | present (repo-local maintainer references) |
| root `install-gemini.*` | present |

## Install targets

| Mode | Installed surface |
|---|---|
| project-local | `<project>/GEMINI.md`, root `<project>/AGENTS.md` when absent, `<project>/.gemini/skills/`, `<project>/.gemini/agents/`, `<project>/.gemini/commands/` |
| global | `~/.gemini/GEMINI.md`, `~/.gemini/AGENTS.md`, `~/.gemini/skills/`, `~/.gemini/agents/`, `~/.gemini/commands/` |

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
3. Treat `src.gemini/` as the source tree for Gemini-specific skills, preview subagents, commands, and future extension packaging.
4. If Orchestrarium shared-routing toggles are needed, use the Gemini `init-project` helper to create `.gemini/.agents-mode` after `/init`.

Important:

- `GEMINI.md` remains owned by Gemini `/init`.
- The installer manages only the `<!-- ORCHESTRARIUM_GEMINI_PACK:... -->` block inside `GEMINI.md`; all content outside that block is preserved on reinstall.
- User-side `@...` imports that live in the installed `GEMINI.md` import block alongside `@./AGENTS.md` are preserved on reinstall.
- Installed runtime uses `AGENTS.md` as the pack-managed shared-governance module imported by `GEMINI.md`. The source tree still keeps `src.gemini/AGENTS.shared.md` as the canonical shared module.
- Installed runtime includes both `.gemini/skills/` and `.gemini/agents/` so the Gemini line can execute the same shared role principle as the neighboring packs.
- `.gemini/settings.json` remains Gemini-native runtime config.
- MCP servers such as Serena, Fetch, or Context7 still belong in `.gemini/settings.json` or `extension/gemini-extension.json`, not inside `AGENTS.md`.
- `.gemini/.agents-mode` is an optional Orchestrarium overlay, not a Gemini-native replacement.
- Decision-driving reads of an existing `.gemini/.agents-mode` overlay must normalize stale, comment-free, or older-layout files to the current canonical format before trusting the flags.
- When `.gemini/.agents-mode` resolves Claude as the external provider, the overlay may also carry `externalClaudeSecretMode` and `externalClaudeApiMode`.
- `externalProvider: auto` resolves through the active named priority profile rather than a Gemini-line Claude default. Explicit same-provider Gemini routing requires an explicit override, and documented repo-local visual-routing heuristics may still keep eligible image, icon, decorative visual, and other clearly visual lanes on Gemini itself when that routing remains honest.
- The overlay also carries `externalPriorityProfile`, `externalPriorityProfiles`, and `externalOpinionCounts`, so a lane can switch between `balanced` and `gemini-crosscheck` and ask for more than one external opinion when the routing policy requires it.
- Independent external adapters may run in parallel when their scopes are independent and provider runtimes support concurrent non-interactive execution. Native internal slot limits are not a reason to silently serialize or drop otherwise-eligible external lanes.
- Bounded parallel external-helper batches should use `external-brigade` instead of trying to inflate `externalOpinionCounts`.

## Validation

```bash
bash src.gemini/scripts/validate-pack.sh .
```

```powershell
.\src.gemini\scripts\validate-pack.ps1
```

## Operator overlay reference

The canonical value-by-value reference for the optional `.gemini/.agents-mode` overlay lives in [docs/agents-mode-reference.md](docs/agents-mode-reference.md). That reference also records task continuity, continue-by-default execution expectations, the named priority profiles, `externalClaudeApiMode`, the repo-local visual-routing heuristic for initialized projects, and the distinction between lane-local opinion counts and brigade-style helper fan-out.

The branch-level docs index and runtime-layout map live in [docs/README.md](docs/README.md) and [docs/provider-runtime-layout.md](docs/provider-runtime-layout.md).

The canonical repo-local Gemini governance and methodology references live in [references-gemini/](references-gemini/README.md).
