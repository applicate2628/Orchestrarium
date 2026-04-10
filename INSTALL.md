# Installation

This monorepo ships two unified entry-point installers at the root (`install.sh` and `install.ps1`). They prompt for Codex, Claude Code, or both, then forward arguments to the matching pack-specific installers in the `scripts/` directory.

The root router currently installs Codex and Claude Code only. The monorepo still carries a first-class Gemini source tree in `src.gemini/` with `GEMINI.md` as its runtime entrypoint and validates that source surface separately.

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
  3) Both
```

For `Both`, the router reuses the same forwarded arguments for both pack-specific installers.

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
- Validation command: `bash src.codex/skills/lead/scripts/validate-skill-pack.sh`.

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
- Completed lead-managed batches now end with one external consultant-check before closure. That check stays advisory-only, but if the external consultant path is disabled or unavailable the batch stays open and the lead escalates instead of silently downgrading.
- Validation command: `bash src.claude/agents/scripts/validate-skill-pack.sh`.

## Dual-platform setup

To install both packs into the same target project, either choose `3) Both` in the router or run both pack-specific installers with the same target arguments.

Expected project-level result:

```text
project/
  AGENTS.md
  .agents/
    skills/
  .claude/
    AGENTS.md
    CLAUDE.md
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

This branch keeps the Gemini line as a validated source tree even though the root router does not install it:

- runtime entrypoint: `src.gemini/GEMINI.md`
- branch-level docs entrypoint: `docs/README.md`
- built-in initialization: Gemini CLI `/init` writes or tailors the project `GEMINI.md`
- expertise layer: `src.gemini/skills/<name>/SKILL.md`
- custom commands: `src.gemini/commands/**/*.toml`
- official runtime config: project `.gemini/settings.json`
- Orchestrarium operator overlay: project `.gemini/.agents-mode`
- extension boundary: `src.gemini/extension/gemini-extension.json`
- provider-local reference tree: `references-gemini/`
- validation command: `bash src.gemini/scripts/validate-pack.sh`
- Orchestrarium overlay bootstrap: `src.gemini/commands/agents/init-project.toml` and `src.gemini/skills/init-project/SKILL.md`

It intentionally follows the official Gemini-preferred layout (`GEMINI.md` + `skills` + `commands` + `extension`) instead of inventing a Claude-like `agents/` source tree. Use Gemini's built-in `/init` for the official `GEMINI.md` bootstrap first. When Orchestrarium needs the same cross-provider routing toggles used on the Codex and Claude lines, initialize the repo-local `.gemini/.agents-mode` overlay separately through the Orchestrarium Gemini init helper rather than replacing Gemini's official `.gemini/settings.json`. When Gemini routes external work to Claude CLI, that overlay may also carry `externalClaudeSecretMode: auto | force`.
