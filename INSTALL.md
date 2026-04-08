# Installation

This repo contains the Claudestrator skill-pack source in `src.claude/`. Install scripts copy it into the target `.claude/` directory. Installing into another machine or repository means running `install.ps1` or `install.sh`.

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
| `src.claude/agents/*.md` (31 files) | `.claude/agents/*.md` | Role definitions |
| `src.claude/agents/contracts/` | `.claude/agents/contracts/` | Handoff templates, routing reference |
| `src.claude/scripts/` | `.claude/scripts/` | Utility scripts (publication-safety scan, validation) |
| `src.claude/agents/team-templates/` | `.claude/agents/team-templates/` | Pre-built team compositions (8 templates) |
| `src.claude/commands/` | `.claude/commands/` | Skills: `/agents-init-project`, `/agents-policies`, `/agents-check-policies` |
| `src.claude/agents/contracts/policies-catalog.md` | `.claude/agents/contracts/policies-catalog.md` | Policy catalog |
| `src.claude/CLAUDE.md` | Merge into target `.claude/CLAUDE.md` | Governance: delegation, hygiene, publication safety, role index |

### Optional

| Source | Destination | Purpose |
| --- | --- | --- |
| `src.claude/memory/` | `.claude/memory/` | Experience-based feedback rules (starts empty if skipped) |

### What NOT to copy

| Path | Why |
| --- | --- |
| `references/` | Skill-pack internal reference docs, not needed at runtime |
| `work-items/` | This repo's task memory — target repo has its own |
| `README.md`, `LICENSE`, `INSTALL.md` | Repo metadata |

### Steps

1. Copy `src.claude/agents/`, `src.claude/commands/`, `src.claude/scripts/` into target repo's `.claude/`
2. Merge `src.claude/CLAUDE.md` content at the TOP of target's `.claude/CLAUDE.md` (prepend). Original user content stays below intact.
3. Optionally copy `src.claude/memory/`
4. Restart Claude
5. Run `/agents-init-project` to configure project policies

## File separation

| Directory | Contents | Installable? |
| --- | --- | --- |
| `src.claude/agents/*.md` | 31 role definitions | Yes |
| `src.claude/agents/contracts/` | Handoff templates, routing reference | Yes |
| `src.claude/scripts/` | Utility scripts (publication-safety scan, validation) | Yes |
| `src.claude/agents/team-templates/` | Pre-built team compositions | Yes |
| `src.claude/commands/` | 19 skills (`/agents-help`, `/agents-init-project`, `/agents-policies`, `/agents-check-policies`, `/agents-validate`, `/agents-check-safety`) | Yes |
| `src.claude/agents/contracts/policies-catalog.md` | Policy catalog with options and defaults | Yes |
| `src.claude/CLAUDE.md` | Governance: delegation, hygiene, publication safety, role index | Yes |
| `src.claude/memory/` | Feedback rules, populated over time | Optional |
| `references/` | Full reference docs (diagrams, translations, strategy) | No — skill-pack internal |
| `work-items/` | This repo's task memory | No — skill-pack internal |

`src.claude/agents/contracts/` is NOT a duplicate of `references/`. It contains the subset of files that role definitions actually reference at runtime.
