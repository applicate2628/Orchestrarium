# Installation

This repo IS a pre-installed Claude Code skill-pack. The `.claude/` directory contains everything Claude Code needs at runtime. Installing into another machine or repository means copying `.claude/` contents to the right location.

## Quick install — current machine (global)

Copy the full skill pack to your global Claude config:

```bash
cp -r .claude/agents/ ~/.claude/agents/
cp -r .claude/memory/ ~/.claude/memory/        # optional
```

## Install into a target repository

### What to copy

| Source | Destination | Purpose |
| --- | --- | --- |
| `.claude/agents/*.md` (31 files) | `.claude/agents/*.md` | Role definitions |
| `.claude/agents/contracts/` | `.claude/agents/contracts/` | Handoff templates, routing reference |
| `.claude/agents/scripts/` | `.claude/agents/scripts/` | Publication-safety scan automation |
| `.claude/agents/team-templates/` | `.claude/agents/team-templates/` | Pre-built team compositions (8 templates) |
| `.claude/commands/` | `.claude/commands/` | Skills: `/init-project`, `/policies`, `/check-policies` |
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

1. Copy `.claude/agents/`, `.claude/commands/`, `.claude/policies/` into target repo's `.claude/`
2. Merge `.claude/CLAUDE.md` content at the TOP of target's `.claude/CLAUDE.md` (prepend). Original user content stays below intact.
3. Optionally copy `.claude/memory/`
4. Restart Claude
5. Run `/init-project` to configure project policies

## File separation

| Directory | Contents | Installable? |
| --- | --- | --- |
| `.claude/agents/*.md` | 31 role definitions | Yes |
| `.claude/agents/contracts/` | Handoff templates, routing reference | Yes |
| `.claude/agents/scripts/` | Publication-safety scan | Yes |
| `.claude/agents/team-templates/` | Pre-built team compositions | Yes |
| `.claude/commands/` | Skills (`/init-project`, `/policies`, `/check-policies`) | Yes |
| `.claude/policies/` | Policy catalog with options and defaults | Yes |
| `.claude/CLAUDE.md` | Governance: delegation, hygiene, publication safety, role index | Yes |
| `.claude/memory/` | Feedback rules, populated over time | Optional |
| `references/` | Full reference docs (diagrams, translations, strategy) | No — skill-pack internal |
| `work-items/` | This repo's task memory | No — skill-pack internal |

`.claude/agents/contracts/` is NOT a duplicate of `references/`. It contains the subset of files that role definitions actually reference at runtime.
