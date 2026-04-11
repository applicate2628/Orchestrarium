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

> **Note:** Global install makes agents and skills available everywhere and seeds `~/.claude/.agents-mode` with the current default overlay. Project-specific policies (`## Project policies` in CLAUDE.md) and project-local Claude-line overrides still belong in each repo where you run `/agents-init-project`. On the Claude line, `externalProvider: auto` resolves through the active named priority profile across `codex`, `claude`, and `gemini`; the canonical Claude-line config may include `externalClaudeSecretMode` and `externalClaudeApiMode` when the resolved provider is `claude`, while `externalClaudeProfile` remains Codex-line only. The active profile or a documented repo-local visual heuristic may rank Gemini first for image/icon/decorative visual work. `externalOpinionCounts` is a same-lane distinct-opinion contract, not a cap on parallel helper multiplicity; use the brigade surface when you need bounded same-provider fan-out.

### Practical external launch rules

| Situation | Rule |
| --- | --- |
| PowerShell Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.ps1`. It accepts both `-PrintSecretPath` and `--print-secret-path` and must remain compatible with Windows PowerShell 5.1 and PowerShell 7+. |
| Bash or Git Bash Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.sh`. It resolves `claude-api`, `claude-api.cmd`, or `claude-api.exe`; if the active shell still cannot see the transport, set `CLAUDE_API_BIN` explicitly. |
| Plain Claude CLI is not logged in | Prefer the allowed Claude API transport instead of repeatedly retrying a plain `claude` command that cannot authenticate. |
| Codex commit review from an external lane | Use `codex review --commit <sha>` without a free-form prompt. If custom review instructions are needed, prefer a narrower `codex exec` run on the admitted scope. |
| Wide release or parity audits | Split the admitted scope by repo, file set, or lane instead of launching one mega neutral-dir prompt across the whole pack family. |

## Install into a target repository

### What to copy

| Source | Destination | Purpose |
| --- | --- | --- |
| `src.claude/agents/*.md` (33 files: 31 indexed roles + 2 external adapters) | `.claude/agents/*.md` | Role definitions |
| `src.claude/agents/contracts/` | `.claude/agents/contracts/` | Handoff templates, routing reference |
| `src.claude/agents/scripts/` | `.claude/agents/scripts/` | Utility scripts (publication-safety scan, validation, Claude API wrapper) |
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
5. Run `/agents-init-project` to configure project policies and review or update the installed default `.claude/.agents-mode`

## File separation

| Directory | Contents | Installable? |
| --- | --- | --- |
| `src.claude/agents/*.md` | 33 role-definition files: 31 indexed roles + 2 external adapters | Yes |
| `src.claude/agents/contracts/` | Handoff templates, routing reference, and the external-dispatch contract | Yes |
| `src.claude/agents/scripts/` | Utility scripts (publication-safety scan, validation, Claude API wrapper) | Yes |
| `src.claude/agents/team-templates/` | Pre-built team compositions | Yes |
| `src.claude/skills/` | 20 slash skills (`/agents-help`, `/agents-second-opinion`, `/agents-init-project`, `/agents-policies`, `/agents-check-policies`, `/agents-validate`, `/agents-check-safety`, `/agents-external-brigade`, ...) | Yes |
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
- project policies and Claude-line operator state (run `/agents-init-project` to review or update repo-local overrides interactively)

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
