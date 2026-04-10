# Installation

This monorepo ships unified entry-point installers at the root (`install.sh` and `install.ps1`). They prompt for Codex, Claude Code, Gemini CLI, or all three, then forward arguments to the matching pack-specific installers in the `scripts/` directory.

## Quick install

Run the router installer from the repository root:

```bash
bash install.sh --global
```

```powershell
.\install.ps1 -Global
```

Or install into a specific project:

```bash
bash install.sh --target /path/to/project
```

```powershell
.\install.ps1 -Target "D:\path\to\project"
```

The router asks which pack to install:

```text
What to install?
  1) Codex pack
  2) Claude Code
  3) Gemini CLI
  4) All three
```

For `All three`, the router reuses the same forwarded arguments for all three pack-specific installers.

## Codex install details

Use `scripts/install-codex.sh` or `scripts/install-codex.ps1` when you want the Codex pack directly.

| Command | Result |
| --- | --- |
| `bash scripts/install-codex.sh --global` | Installs into `~/.codex/` |
| `bash scripts/install-codex.sh --target /path/to/project` | Installs into the target project's `.agents/skills/` and merges root `AGENTS.md` |
| `.\scripts\install-codex.ps1 -Global` | Installs into `~/.codex/` |
| `.\scripts\install-codex.ps1 -Target "D:\path\to\project"` | Installs into the target project's `.agents/skills/` and merges root `AGENTS.md` |

Notes:

- Project-level Codex installs use `.agents/skills/` plus the project root `AGENTS.md`.
- Project-level installs ensure `/.reports/` is present in the target repo `.gitignore` if it is missing, because session logs are local-only runtime output.
- The canonical project-local config file is `.agents/.agents-mode`; legacy `.agents/.consultant-mode` is fallback-only during migration.
- First-time creation should write the full default shape with inline comments listing allowed values for each key.
- `consultantMode` still controls `$consultant`; `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation an explicit standing instruction whenever a matching specialist and viable tool path exist; `mcpMode: auto` lets the agent decide when MCP is appropriate while `force` makes MCP usage an explicit standing instruction; the two `preferExternal*` flags let routing prefer `$external-worker` and `$external-reviewer`; and `externalProvider: auto` keeps the line default external CLI unless the operator explicitly selects another installed provider such as `gemini`.
- `externalClaudeSecretMode` is used whenever the selected external provider is Claude CLI: `auto` keeps the first Claude call plain and allows one SECRET-backed retry only after quota, limit, or reset errors; `force` applies `ANTHROPIC_*` from the local Claude `SECRET.md` to the primary Claude call.
- `externalClaudeProfile` is Codex-line only and selects the Claude CLI execution profile: `sonnet-high` maps to Sonnet with `--effort high`, and `opus-max` maps to Opus with `--effort max`.
- Full mode tables live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
- After first-time Codex project install, run `$init-project` in Codex to write `## Project policies` to the root `AGENTS.md` and initialize `.agents/.agents-mode`.
- Completed lead-managed batches now end with one external consultant-check before closure. That check stays advisory-only, but if the external consultant path is disabled or unavailable the batch stays open and the lead escalates instead of silently downgrading.
- Validation commands: `bash src.codex/skills/lead/scripts/validate-skill-pack.sh` or `.\src.codex\skills\lead\scripts\validate-skill-pack.ps1`.

## Claude Code install details

Use `scripts/install-claude.sh` or `scripts/install-claude.ps1` when you want the Claude Code pack directly.

| Command | Result |
| --- | --- |
| `bash scripts/install-claude.sh --global` | Installs into `~/.claude/` |
| `bash scripts/install-claude.sh --target /path/to/project` | Installs into the target project's `.claude/` |
| `.\scripts\install-claude.ps1 -Global` | Installs into `~/.claude/` |
| `.\scripts\install-claude.ps1 -Target "D:\path\to\project"` | Installs into the target project's `.claude/` |

Notes:

- Project-level Claude installs create or update `.claude/AGENTS.md` and `.claude/CLAUDE.md`.
- Project-level installs ensure `/.reports/` is present in the target repo `.gitignore` if it is missing, because session logs are local-only runtime output.
- Claude memory is shipped in `src.claude/memory/` and preserved across reinstalls by the existing installer behavior.
- User-side Claude imports such as `@memory/...` are preserved across reinstalls when they live in the installed `.claude/CLAUDE.md` import block alongside `@AGENTS.md`.
- The canonical project-local config file is `.claude/.agents-mode`; legacy `.claude/.consultant-mode` is fallback-only during migration.
- First-time creation should write the full default shape with inline comments listing allowed values for each key.
- `consultantMode` still controls `$consultant`; `delegationMode: manual` keeps explicit-permission behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation an explicit standing instruction whenever a matching specialist and viable tool path exist; `mcpMode: auto` lets the agent decide when MCP is appropriate while `force` makes MCP usage an explicit standing instruction; the two `preferExternal*` flags let routing prefer `$external-worker` and `$external-reviewer`; and `externalProvider: auto` keeps the Claude-line default external CLI unless the operator explicitly selects another installed provider such as `gemini`.
- Claude-line external dispatch uses Codex CLI, so the Claude-target keys `externalClaudeSecretMode` and `externalClaudeProfile` are not part of the Claude-line canonical config.
- Full mode tables live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
- After first-time Claude project install, run `/agents-init-project` in Claude Code to write `## Project policies` in `.claude/CLAUDE.md` and initialize `.claude/.agents-mode`.
- Completed lead-managed batches now end with one external consultant-check before closure. That check stays advisory-only, but if the external consultant path is disabled or unavailable the batch stays open and the lead escalates instead of silently downgrading.
- Validation commands: `bash src.claude/agents/scripts/validate-skill-pack.sh` or `.\src.claude\agents\scripts\validate-skill-pack.ps1`.

## Gemini CLI install details

Use `scripts/install-gemini.sh` or `scripts/install-gemini.ps1` when you want the Gemini pack directly.

| Command | Result |
| --- | --- |
| `bash scripts/install-gemini.sh --global` | Installs into `~/.gemini/` including `skills/`, `agents/`, and `commands/` |
| `bash scripts/install-gemini.sh --target /path/to/project` | Installs into the target project's `GEMINI.md`, root `AGENTS.md` when absent, and `.gemini/skills`, `.gemini/agents`, `.gemini/commands` |
| `.\scripts\install-gemini.ps1 -Global` | Installs into `~/.gemini/` including `skills/`, `agents/`, and `commands/` |
| `.\scripts\install-gemini.ps1 -Target "D:\path\to\project"` | Installs into the target project's `GEMINI.md`, root `AGENTS.md` when absent, and `.gemini/skills`, `.gemini/agents`, `.gemini/commands` |

Notes:

- Project-level Gemini installs preserve any user-owned content outside the managed Orchestrarium block inside `GEMINI.md`.
- User-side `@...` imports that live in the installed `GEMINI.md` import block alongside `@./AGENTS.md` are preserved across reinstalls.
- Gemini installs materialize the shared-governance layer as `AGENTS.md`; `GEMINI.md` loads it through the official `@./AGENTS.md` import. Project installs preserve an existing root `AGENTS.md` instead of overwriting it.
- Gemini installs materialize both the stable expertise catalog in `.gemini/skills/` and the preview specialist-team layer in `.gemini/agents/`.
- Gemini runtime config and MCP wiring remain owned by `.gemini/settings.json` and `gemini-extension.json`; servers such as Serena, Fetch, or Context7 do not belong inside `AGENTS.md`.
- The optional Orchestrarium overlay file is `.gemini/.agents-mode`.
- After first-time Gemini project install, run Gemini CLI `/init` if you want Gemini to create or refresh the user-owned portion of `GEMINI.md`, and then use the Orchestrarium Gemini `init-project` helper only if you also want `.gemini/.agents-mode`.
- Validation commands: `bash src.gemini/scripts/validate-pack.sh` or `.\src.gemini\scripts\validate-pack.ps1`.

## Multi-pack setup

To install any combination of packs into the same target project, either choose the matching option in the router or run the pack-specific installers with the same target arguments.

Expected project-level result:

```text
project/
  AGENTS.md
  GEMINI.md
  .agents/
    skills/
  .claude/
    AGENTS.md
    CLAUDE.md
  .gemini/
    skills/
    agents/
    commands/
```

Reference directories are development-only and are not installed:

- `shared/references/`
- `docs/`
- `references-codex/`
- `references-claude/`
- `references-gemini/`

That split is intentional. `shared/references/` holds the canonical shared design cores, `docs/` is the common branch-level docs surface, and `references-codex/`, `references-claude/`, and `references-gemini/` keep only pack-local addenda or compatibility pointers. `subagent-operating-model` is the main example: the installed packs keep their runtime docs, but the monorepo now keeps one shared blueprint core plus one addendum per pack instead of near-duplicate full reference copies.

## Post-install customization

Customize each platform in the place that platform actually reads:

- Codex: append project-specific rules below the installed section in the project root `AGENTS.md`.
- Claude Code: append project-specific rules below the installed section in `.claude/CLAUDE.md`.
- Claude Code: user-side `@...` imports in `.claude/CLAUDE.md` may live in the import block near `@AGENTS.md`; the installer preserves those imports on reinstall.
- Configure consultant and external-dispatch preferences in `.agents/.agents-mode` for Codex or `.claude/.agents-mode` for Claude Code.
- Shared design references in `shared/references/` are repository-maintainer documentation only; they are not copied into target projects and should not be treated as installed runtime docs.

When both packs are installed, keep shared project policies aligned across both files. The repository's dev overlays, `AGENTS.md` and `CLAUDE.md`, are for maintaining this monorepo and are not copied into target projects by the install scripts.

## Gemini source tree in the monorepo

The monorepo still keeps the full Gemini line as a validated source tree in addition to the new root-router install path:

- runtime entrypoint: `src.gemini/GEMINI.md`
- shared-governance import module: `src.gemini/AGENTS.shared.md`
- branch-level docs entrypoint: `docs/README.md`
- built-in initialization: Gemini CLI `/init` writes or tailors the project `GEMINI.md`
- expertise layer: `src.gemini/skills/<name>/SKILL.md`
- preview specialist-team layer: `src.gemini/agents/*.md`
- repo-local team templates: `src.gemini/agents/team-templates/*.json`
- custom commands: `src.gemini/commands/**/*.toml`
- official runtime config: project `.gemini/settings.json`
- Orchestrarium operator overlay: project `.gemini/.agents-mode`
- extension boundary: `src.gemini/extension/gemini-extension.json`
- provider-local reference tree: `references-gemini/`
- validation commands: `bash src.gemini/scripts/validate-pack.sh` or `.\src.gemini\scripts\validate-pack.ps1`
- Orchestrarium overlay bootstrap: `src.gemini/commands/agents/init-project.toml` and `src.gemini/skills/init-project/SKILL.md`

It intentionally combines the official stable Gemini surfaces (`GEMINI.md`, imported markdown modules, `skills`, `commands`, `extension`) with the official preview `agents/` surface so the Gemini line can carry the same shared role principle as the Codex and Claude packs without lying about provider ownership. Use Gemini's built-in `/init` for the official `GEMINI.md` bootstrap first. When Orchestrarium needs the same cross-provider routing toggles used on the Codex and Claude lines, initialize the repo-local `.gemini/.agents-mode` overlay separately through the Orchestrarium Gemini init helper rather than replacing Gemini's official `.gemini/settings.json`. MCP wiring for servers such as Serena, Fetch, or Context7 remains a `settings.json` or `gemini-extension.json` concern. When Gemini routes external work to Claude CLI, that overlay may also carry `externalClaudeSecretMode: auto | force`. Full operator semantics, including task continuity and continue-by-default execution expectations, live in [`docs/agents-mode-reference.md`](docs/agents-mode-reference.md).
