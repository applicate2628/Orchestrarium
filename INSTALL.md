# Installation

This repo IS a pre-installed Claude Code skill-pack. The `.claude/` directory contains everything Claude Code needs at runtime. Installing into another machine or repository means copying `.claude/` contents to the right location.

## Quick install — current machine (global)

```powershell
# PowerShell (Windows)
.\install.ps1 -Global
```

```bash
# Bash (macOS / Linux / Git Bash)
bash install.sh --global
```

## Install into a specific repo

```powershell
.\install.ps1 -Target "D:\my-repo"
```

```bash
bash install.sh --target /path/to/repo
```

## Install into current repo (default)

```powershell
.\install.ps1
```

```bash
bash install.sh
```

The scripts handle clean removal of old files, copying, CLAUDE.md merging, and file-level verification. Re-running = reinstall. Memory is preserved across reinstalls.

> **Note:** Global install makes agents and skills available everywhere. Project-specific policies (`## Project policies` in CLAUDE.md) are still per-repo — run `/agents-init-project` in each repo where you want them.

## Install into a target repository

### What to copy

| Source | Destination | Purpose |
| --- | --- | --- |
| `.claude/agents/*.md` (31 files) | `.claude/agents/*.md` | Role definitions |
| `.claude/agents/contracts/` | `.claude/agents/contracts/` | Handoff templates, routing reference |
| `.claude/scripts/` | `.claude/scripts/` | Utility scripts (publication-safety scan, validation) |
| `.claude/agents/team-templates/` | `.claude/agents/team-templates/` | Pre-built team compositions (8 templates) |
| `.claude/commands/` | `.claude/commands/` | Skills: `/agents-init-project`, `/agents-policies`, `/agents-check-policies` |
| `.claude/policies/` | `.claude/policies/` | Policy catalog with configurable options |
| `.claude/CLAUDE.md` | Merge into target `.claude/CLAUDE.md` | Governance: delegation, hygiene, publication safety, role index |

### Optional

| Source | Destination | Purpose |
| --- | --- | --- |
| `.claude/memory/` | `.claude/memory/` | Experience-based feedback rules (starts empty if skipped) |

### What NOT to copy

| Path | Why |
| --- | --- |
| `references/` | Skill-pack internal reference docs, not needed at runtime |
| `work-items/` | This repo's task memory — target repo has its own |
| `README.md`, `LICENSE`, `INSTALL.md` | Repo metadata |

### Steps

1. Copy `.claude/agents/`, `.claude/commands/`, `.claude/policies/`, `.claude/scripts/` into target repo's `.claude/`
2. Merge `.claude/CLAUDE.md` content at the TOP of target's `.claude/CLAUDE.md` (prepend). Original user content stays below intact.
3. Optionally copy `.claude/memory/`
4. Restart Claude
5. Run `/agents-init-project` to configure project policies

## File separation

| Directory | Contents | Installable? |
| --- | --- | --- |
| `.claude/agents/*.md` | 31 role definitions | Yes |
| `.claude/agents/contracts/` | Handoff templates, routing reference | Yes |
| `.claude/scripts/` | Utility scripts (publication-safety scan, validation) | Yes |
| `.claude/agents/team-templates/` | Pre-built team compositions | Yes |
| `.claude/commands/` | 13 skills (`/agents-help`, `/agents-init-project`, `/agents-policies`, `/agents-check-policies`, `/agents-validate`, `/agents-check-safety`) | Yes |
| `.claude/policies/` | Policy catalog with options and defaults | Yes |
| `.claude/CLAUDE.md` | Governance: delegation, hygiene, publication safety, role index | Yes |
| `.claude/memory/` | Feedback rules, populated over time | Optional |
| `references/` | Full reference docs (diagrams, translations, strategy) | No — skill-pack internal |
| `work-items/` | This repo's task memory | No — skill-pack internal |

`.claude/agents/contracts/` is NOT a duplicate of `references/`. It contains the subset of files that role definitions actually reference at runtime.
