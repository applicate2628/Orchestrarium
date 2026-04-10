# Provider Runtime Layouts

This document records the installed runtime layout for the provider lines used by Orchestrarium today, including provider source trees that already exist in the monorepo. It is an install/runtime reference, not a source-layout reference.

Do not confuse these runtime surfaces with the monorepo authoring trees such as `src.codex/`, `src.claude/`, or `src.gemini/`.

Read the tables with three layers in mind:

- `Official provider behavior` means the provider's own documented runtime surface or configuration model.
- `Orchestrarium runtime contract` means the install shape and conventions introduced by this repository.
- `Observed installed behavior` means the result verified in an installed target.

Do not collapse those layers into one claim. When a row is Orchestrarium-owned rather than provider-native, the notes call that out explicitly.

## Scope legend

| Scope | Meaning |
| --- | --- |
| `Global` | User-level installed runtime surface, usually under the provider's home directory |
| `Local` | Project-level installed runtime surface inside the current repository or target project |

## Codex

### Global

| Item | Path or shape | Notes |
| --- | --- | --- |
| Installed pack root | `~/.codex/` | Global Codex pack install target |
| Governance entrypoint | `~/.codex/AGENTS.md` | Installed Codex runtime entrypoint |
| Skill tree | `~/.codex/skills/<role>/SKILL.md` | Orchestrarium Codex runtime organizes each role as a skill directory |
| Validation script | `~/.codex/skills/lead/scripts/validate-skill-pack.sh` | Same lead script tree as the repo source |
| Publication-safety scan | `~/.codex/skills/lead/scripts/check-publication-safety.sh` | PowerShell wrapper exists alongside the shell script |
| Project-local state | `<project>/.agents/.agents-mode` | Even with a global Codex install, Orchestrarium keeps operator-routing state project-local |

### Local

| Item | Path or shape | Notes |
| --- | --- | --- |
| Installed pack root | `<project>/.agents/skills/` | Role skills are copied here |
| Governance entrypoint | `<project>/AGENTS.md` | Codex pack section is merged into the project-root `AGENTS.md` |
| Skill tree | `<project>/.agents/skills/<role>/SKILL.md` | Mirrors the global `skills/` structure |
| Local config | `<project>/.agents/.agents-mode` | Canonical Orchestrarium local state file; legacy fallback is `.agents/.consultant-mode` |
| Validation script | `<project>/.agents/skills/lead/scripts/validate-skill-pack.sh` | Run from the target project root after install |
| Publication-safety scan | `<project>/.agents/skills/lead/scripts/check-publication-safety.sh` | PowerShell wrapper exists alongside the shell script |

## Claude Code

### Global

| Item | Path or shape | Notes |
| --- | --- | --- |
| Global context file | `~/.claude/CLAUDE.md` | Official user-level Claude Code instruction file |
| Global personal skills | `~/.claude/skills/<skill-name>/SKILL.md` | Official preferred user-level extension surface |
| Global personal subagents | `~/.claude/agents/*.md` | Official user-level custom subagent surface |
| Global legacy commands | `~/.claude/commands/*.md` | Still supported, but Claude docs now recommend skills as the preferred model |
| Project-local state | `<project>/.claude/.agents-mode` | Orchestrarium repo-local operator state; this is not a Claude-native file from official docs |

### Local

| Item | Path or shape | Notes |
| --- | --- | --- |
| Project context file | `<project>/.claude/CLAUDE.md` or `<project>/CLAUDE.md` | Official project-level Claude instruction entrypoints |
| Local personal override | `<project>/CLAUDE.local.md` | Official personal, uncommitted project override layer |
| Project skills | `<project>/.claude/skills/<skill-name>/SKILL.md` | Official preferred project-level extension surface |
| Project subagents | `<project>/.claude/agents/*.md` | Official project-level custom subagent surface |
| Legacy commands | `<project>/.claude/commands/*.md` | Still work, but lose precedence to a skill with the same name |
| Orchestrarium shared governance copy | `<project>/.claude/AGENTS.md` | Repo-local overlay copied by Orchestrarium install scripts; not a Claude-native runtime requirement |
| Orchestrarium local config | `<project>/.claude/.agents-mode` | Canonical Orchestrarium local state file; legacy fallback is `.claude/.consultant-mode` |
| Pack memory | `<project>/.claude/memory/` | Repo-local installed memory payload for the Orchestrarium Claude pack |

## Gemini CLI

### Global

| Item | Path or shape | Notes |
| --- | --- | --- |
| Global context file | `~/.gemini/GEMINI.md` | Official user-level Gemini context file |
| Global shared-governance import | `~/.gemini/AGENTS.md` | Orchestrarium-installed markdown module imported by `GEMINI.md`; not a Gemini-native required filename |
| Global user skills | `~/.gemini/skills/` | Official user-level skill location |
| Global user skills alias | `~/.agents/skills/` | Official alias; within the user tier, the alias takes precedence over `~/.gemini/skills/` |
| Global user subagents | `~/.gemini/agents/` | Official preview user-level subagent location; Orchestrarium uses it for the specialist-team layer |
| Global custom commands | `~/.gemini/commands/` | Official user-level Gemini custom commands |
| Global settings | `~/.gemini/settings.json` | Official CLI configuration, including optional `context.fileName` overrides |
| Global extensions | `~/.gemini/extensions/<extension>/` | Official runtime location for installed or linked extensions |
| Extension manifest | `gemini-extension.json` inside an extension | Official extension manifest; extensions can bundle skills, commands, context, and MCP servers |

### Local

| Item | Path or shape | Notes |
| --- | --- | --- |
| Project context file | `<project>/GEMINI.md` | Official default project-level Gemini context file; built-in `/init` generates or tailors this file |
| Project shared-governance import | `<project>/AGENTS.md` | Orchestrarium-installed markdown module imported by `GEMINI.md`; not a Gemini-native required filename |
| Parent-context hierarchy | `<project>/../GEMINI.md` up to project root | Gemini walks parent directories until the `.git` root |
| Sub-directory context | `<project>/<subdir>/GEMINI.md` | Gemini also loads more specific context files below the current working directory |
| Workspace skills | `<project>/.gemini/skills/` | Official workspace skill location |
| Workspace skills alias | `<project>/.agents/skills/` | Official alias; within the workspace tier, the alias takes precedence over `.gemini/skills/` |
| Workspace subagents | `<project>/.gemini/agents/` | Official preview project-level subagent location; Orchestrarium installs the specialist-team layer here |
| Workspace custom commands | `<project>/.gemini/commands/` | Official project-local Gemini custom commands |
| Workspace settings | `<project>/.gemini/settings.json` | Official project-local Gemini settings |
| Orchestrarium operator overlay | `<project>/.gemini/.agents-mode` | Repo-local shared routing overlay for consultant, delegation, MCP, and external-provider preferences; not a Gemini-native settings surface and should be initialized separately after Gemini `/init` |
| Optional context filename override | `context.fileName` in settings | `AGENTS.md` is not a default Gemini entrypoint; Orchestrarium uses `GEMINI.md` imports instead of taking over this settings-owned surface |
| Extension-provided skills | installed extension content | Official third discovery tier after workspace and user skills |
| Important overlap note | workspace `.agents/skills/` | If a repository already uses `.agents/skills/` for Codex, Gemini will also discover those skills because this alias is official Gemini behavior |

## Quick comparison

| Provider | Global runtime root | Local runtime root | Native instruction entrypoint |
| --- | --- | --- | --- |
| Codex | `~/.codex/` | `<project>/.agents/` plus root `AGENTS.md` | `AGENTS.md` |
| Claude Code | `~/.claude/` | `<project>/.claude/` and optional root `CLAUDE.md` | `CLAUDE.md` |
| Gemini CLI | `~/.gemini/` | `<project>/.gemini/` plus `GEMINI.md` hierarchy | `GEMINI.md` |

## Sources

- Orchestrarium install and runtime contracts: `INSTALL.md`, `src.codex/AGENTS.codex.md`, `src.codex/skills/consultant/SKILL.md`, `src.claude/CLAUDE.md`, `src.claude/agents/consultant.md`, `scripts/install-codex.sh`, `scripts/install-codex.ps1`, `scripts/install-claude.sh`, `scripts/install-claude.ps1`
- Claude Code documentation:
  - Memory and `CLAUDE.md` locations: <https://code.claude.com/docs/en/memory>
  - Skills and legacy commands: <https://code.claude.com/docs/en/slash-commands>
  - Subagents: <https://code.claude.com/docs/en/sub-agents>
- Gemini CLI documentation:
  - `GEMINI.md` hierarchy: <https://google-gemini.github.io/gemini-cli/docs/cli/gemini-md.html>
  - Agent skills discovery tiers and aliases: <https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/cli/skills.md>
  - Creating skills: <https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/cli/creating-skills.md>
  - Custom commands: <https://google-gemini.github.io/gemini-cli/docs/cli/custom-commands.html>
  - Extensions and `gemini-extension.json`: <https://raw.githubusercontent.com/google-gemini/gemini-cli/main/docs/extensions/reference.md>
