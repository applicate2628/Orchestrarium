# Installation

This repo contains the Claudestrator skill-pack source in `src.claude/`. Install scripts copy it into the target `.claude/` directory. Installing into another machine or repository means running `install-claude.ps1` or `install-claude.sh`.

## Quick install — current machine (global)

```powershell
# PowerShell (Windows)
.\install-claude.ps1 -Global
```

```bash
# Bash (macOS / Linux / Git Bash)
bash install-claude.sh --global
```

## Install into a specific repo

```powershell
.\install-claude.ps1 -Target "D:\my-repo"
```

```bash
bash install-claude.sh --target /path/to/repo
```

## Install into current repo (default)

```powershell
.\install-claude.ps1
```

```bash
bash install-claude.sh
```

The scripts handle clean removal of old files, copying, CLAUDE.md merging, and file-level verification. Re-running = reinstall. Memory is preserved across reinstalls.

> **Note:** Global install makes agents and skills available everywhere. Project-specific policies (`## Project policies` in CLAUDE.md) are still per-repo — run `/agents-init-project` in each repo where you want them.

## Install into a target repository

### What to copy

| Source | Destination | Purpose |
| --- | --- | --- |
| `src.claude/agents/*.md` (33 files: 31 indexed roles + 2 external adapters) | `.claude/agents/*.md` | Role definitions |
| `src.claude/agents/contracts/` | `.claude/agents/contracts/` | Handoff templates, routing reference |
| `src.claude/agents/scripts/` | `.claude/agents/scripts/` | Utility scripts (publication-safety scan, validation) |
| `src.claude/agents/team-templates/` | `.claude/agents/team-templates/` | Pre-built team compositions (8 templates) |
| `src.claude/skills/` | `.claude/skills/` | Preferred slash skills: `/agents-init-project`, `/agents-policies`, `/agents-check-policies` |
| `src.claude/agents/contracts/policies-catalog.md` | `.claude/agents/contracts/policies-catalog.md` | Policy catalog |
| `src.claude/CLAUDE.md` | Merge into target `.claude/CLAUDE.md` | Governance: delegation, hygiene, publication safety, role index |

### Optional

| Source | Destination | Purpose |
| --- | --- | --- |
| `src.claude/memory/` | `.claude/memory/` | Experience-based feedback rules (starts empty if skipped) |

### What NOT to copy

| Path | Why |
| --- | --- |
| `references-claude/` | Skill-pack internal reference docs, not needed at runtime |
| `work-items/` | This repo's task memory — target repo has its own |
| `README.md`, `LICENSE`, `INSTALL.md` | Repo metadata |

### Steps

1. Copy `src.claude/agents/`, `src.claude/skills/` into target repo's `.claude/`
2. Merge `src.claude/CLAUDE.md` content at the TOP of target's `.claude/CLAUDE.md` (prepend). Original user content stays below intact.
3. Optionally copy `src.claude/memory/`
4. Restart Claude
5. Run `/agents-init-project` to configure project policies

## File separation

| Directory | Contents | Installable? |
| --- | --- | --- |
| `src.claude/agents/*.md` | 33 role-definition files: 31 indexed roles + 2 external adapters | Yes |
| `src.claude/agents/contracts/` | Handoff templates, routing reference, and the external-dispatch contract | Yes |
| `src.claude/agents/scripts/` | Utility scripts (publication-safety scan, validation) | Yes |
| `src.claude/agents/team-templates/` | Pre-built team compositions | Yes |
| `src.claude/skills/` | 19 slash skills (`/agents-help`, `/agents-second-opinion`, `/agents-init-project`, `/agents-policies`, `/agents-check-policies`, `/agents-validate`, `/agents-check-safety`, ...) | Yes |
| `src.claude/agents/contracts/policies-catalog.md` | Policy catalog with options and defaults | Yes |
| `src.claude/CLAUDE.md` | Governance: delegation, hygiene, publication safety, role index | Yes |
| `src.claude/memory/` | Feedback rules, populated over time | Optional |
| `docs/` | Branch-local docs index, Claude-line `.claude/.agents-mode` reference, and runtime-layout notes | No — maintainer-facing source docs |
| `references-claude/` | Full reference docs (diagrams, translations, strategy) | No — skill-pack internal |
| `work-items/` | This repo's task memory | No — skill-pack internal |

`src.claude/agents/contracts/` is NOT a duplicate of `references-claude/`. It contains the subset of files that role definitions actually reference at runtime.

## Post-install

### How Claude Code discovers governance

Claude Code reads two types of instruction files:

**`CLAUDE.md` (primary governance):**
- Claude Code walks **up** from cwd to root, loading all `CLAUDE.md` and `CLAUDE.local.md` files
- All found files are concatenated (not override) — later content has higher effective priority
- `@path` syntax imports other files inline (e.g., `@AGENTS.md` pulls shared governance)
- Claude Code does **NOT** read `AGENTS.md` automatically — it must be imported via `@AGENTS.md` in `CLAUDE.md`

**`CLAUDE.local.md` (personal, gitignored):**
- Appended after `CLAUDE.md` in each directory
- For personal preferences, local overrides

### Repo-local customization

Add project-specific rules **below** the installed Claudestrator section in `.claude/CLAUDE.md`:

- canonical paths and source-of-truth references
- allowed toolchains, shells, build systems, and concrete build/test commands
- API, config, schema, and migration evolution rules
- project policies (run `/agents-init-project` to configure interactively)

The installed pack occupies the top of `CLAUDE.md` (starting with `@AGENTS.md` import). Your project-specific rules go below it. On reinstall, the pack section is replaced; your rules below it are preserved.

### Dual-platform projects (Codex + Claude Code)

If both packs are installed in the same project:

```
project/
  AGENTS.md           ← Orchestrarium (shared + Codex-specific, read by Codex)
  .claude/
    AGENTS.md         ← shared governance (read by Claude Code via @import)
    CLAUDE.md         ← @AGENTS.md + Claude-specific rules
```

Shared governance is duplicated because Codex reads root `AGENTS.md` while Claude Code reads `.claude/AGENTS.md`. Both are generated from the same `AGENTS.shared.md` source.
