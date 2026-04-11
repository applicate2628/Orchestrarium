# Installation

This repo contains the Orchestrarium skill-pack source in `src.codex/`. Install scripts copy it into the correct target locations. The target structure depends on the install mode.

## Quick install — current machine (global)

```powershell
# PowerShell (Windows)
.\install-codex.ps1 -Global
```

```bash
# Bash (macOS / Linux / Git Bash)
bash install-codex.sh --global
```

Global install copies everything into `~/.codex/` (mirrors `src.codex/` structure).

## Install into a specific repo

```powershell
.\install-codex.ps1 -Target "D:\my-repo"
```

```bash
bash install-codex.sh --target /path/to/repo
```

Repo-level install places skills into `.agents/skills/`, merges `AGENTS.md` into the project root, and seeds the default operator file at `.agents/.agents-mode`.

## Install into current repo (default)

```powershell
.\install-codex.ps1
```

```bash
bash install-codex.sh
```

## Install target mapping

| Source | Global (`--global`) | Repo-level (default / `--target`) |
| --- | --- | --- |
| `src.codex/skills/` | `~/.codex/skills/` | `.agents/skills/` |
| `src.codex/skills/lead/scripts/` | `~/.codex/skills/lead/scripts/` | `.agents/skills/lead/scripts/` |
| `src.codex/AGENTS.shared.md` + `src.codex/AGENTS.codex.md` | Merge into `~/.codex/AGENTS.md` | Merge into root `AGENTS.md` |

The scripts handle clean removal of old files, copying, AGENTS.md merging, and file-level verification. Re-running = reinstall.

Operator state lives in the installed target: repo installs seed `.agents/.agents-mode`, while global installs seed `~/.codex/.agents-mode`.

The canonical Codex-line operator shape is:
- `consultantMode`
- `delegationMode`
- `mcpMode`
- `preferExternalWorker`
- `preferExternalReviewer`
- `externalProvider`
- `externalPriorityProfile`
- `externalPriorityProfiles`
- `externalOpinionCounts`
- `externalCodexWorkdirMode`
- `externalClaudeWorkdirMode`
- `externalGeminiWorkdirMode`
- `externalClaudeSecretMode`
- `externalClaudeApiMode`
- `externalClaudeProfile`

`externalPriorityProfile` selects the active named routing profile, with `balanced` as the ordinary default and `gemini-crosscheck` as the named profile that promotes Gemini into cross-check work when more than one independent external opinion is requested. `externalPriorityProfiles` stores the profile-specific lane ordering data; missing `balanced` means the current shared lane matrix. `externalOpinionCounts` stores how many distinct external opinions each lane should collect; missing counts default to `1`.

`externalProvider: auto` resolves through the active priority profile and requested opinion count, not by host pack. Provider-specific workdir keys default to neutral so comparative or external runs do not inherit repo-local instruction overlays by cwd alone. Explicit `codex`, `claude`, or `gemini` may be selected when routing asks for them, and documented repo-local visual heuristics may still prefer Gemini for image generation, icon work, and decorative visual lanes when that routing remains honest. `externalClaudeApiMode` is the named Claude secondary-transport toggle: `disabled` forbids `claude-api`, `auto` keeps `claude-api` as the fallback after the allowed Claude CLI path is exhausted, and `force` uses `claude-api` as the primary Claude transport immediately.

Project policies are configured as a `## Project policies` section in the target `AGENTS.md`, not as a separate directory. See `skills/lead/policies-catalog.md` for available policy options.

After first-time project install, run `$init-project` to write `## Project policies` in the root `AGENTS.md` and review or update the installed default `.agents/.agents-mode`.

## File separation

| Directory | Contents | Installable? |
| --- | --- | --- |
| `src.codex/skills/<role>/SKILL.md` | 33 role definitions: 31 indexed roles + 2 external adapters, plus 2 utility skills | Yes |
| `src.codex/skills/<role>/agents/openai.yaml` | Display metadata and default prompt | Yes |
| `src.codex/skills/lead/` | Operating-model notes, handoff contracts | Yes |
| `src.codex/skills/consultant/` | Consultant role: toggle logic, execution paths, inline Claude CLI invocation | Yes |
| `src.codex/skills/second-opinion/` | Consultant toggle and explicit invocation | Yes |
| `src.codex/skills/lead/scripts/` | Publication safety scan, validation | Yes |
| `src.codex/skills/lead/policies-catalog.md` | Policy options reference (installed with skills) | Yes |
| `src.codex/skills/external-brigade/` | Bounded parallel external helper orchestration | Yes |
| `src.codex/AGENTS.shared.md` + `src.codex/AGENTS.codex.md` | Governance: delegation, hygiene, publication safety, role index | Yes |
| `docs/` | Branch-local docs index, runtime-layout notes, `.agents/.agents-mode` reference | No — maintainer-facing source docs |
| `references-codex/` | Full reference docs (diagrams, translations, strategy) | No — skill-pack internal |

## Post-install

The pack is self-contained. No files from this development repository's root are needed at runtime.

### How Codex discovers governance and config

Codex reads two kinds of project-level files:

**`AGENTS.md` (governance — rules, delegation, hygiene):**
- Codex searches from project root **down** to the current working directory
- One file per directory; `AGENTS.override.md` takes priority over `AGENTS.md` in the same directory
- Content closer to cwd appears later in prompt and effectively overrides earlier content
- `.codex/AGENTS.md` or `.agents/AGENTS.md` are **NOT** read — Codex only reads `AGENTS.md` in directories on the root→cwd path
- The install script places the pack `AGENTS.md` in the project root — this is the only location Codex will read it from

**`.codex/config.toml` (configuration — model, sandbox, approval policy):**
- Global: `~/.codex/config.toml`
- Project: `<project>/.codex/config.toml` (read only if the project is trusted)
- Closest to cwd wins
- Use for: model overrides, sandbox mode, approval policy, MCP servers — not for governance rules

### Repo-local customization

Add project-specific rules **below** the installed Orchestrarium section in root `AGENTS.md`:

- canonical paths and source-of-truth references
- allowed toolchains, shells, build systems, and concrete build/test commands
- API, config, schema, and migration evolution rules
- rollback expectations, rollout rules, and project-specific budgets or SLAs
- repository-specific portability assumptions
- configured task-memory directory and recovery policy
- project policies (see `skills/lead/policies-catalog.md` for options)

The installed pack occupies the top of `AGENTS.md`. Your project-specific rules go below it. On reinstall, the pack section is replaced; your rules below it are preserved. Content lower in the file has higher effective priority — your project rules override pack defaults where they conflict.

### Dual-platform projects (Codex + Claude Code)

If both Orchestrarium and Claudestrator are installed in the same project:

```
project/
  AGENTS.md           ← Orchestrarium (shared + Codex-specific, read by Codex)
  .claude/
    AGENTS.md         ← Claudestrator shared governance (read by Claude Code via @import)
    CLAUDE.md         ← @AGENTS.md + Claude-specific rules
```

Shared governance (hygiene rules, delegation principles, role index) is duplicated in both locations because Codex and Claude Code read from different paths. Both are generated from the same `AGENTS.shared.md` source, so content stays in sync across reinstalls.

To add project-specific rules that apply to both platforms:
1. Add rules to root `AGENTS.md` (below the pack section) — Codex reads them directly
2. Claude Code reads `.claude/CLAUDE.md` which imports `.claude/AGENTS.md` — to add project rules for Claude Code, edit `.claude/CLAUDE.md` below the pack section

## Portability

### Claude CLI invocation

`consultant/SKILL.md` includes Claude CLI invocation examples for both macOS/Linux and Windows.

- **macOS / Linux**: uses `claude` directly.
- **Windows**: uses `cmd.exe /c claude.exe` (or `claude.cmd` as fallback) to work inside Git Bash environments where Codex typically runs.
- `externalClaudeSecretMode: auto` keeps the first Claude call plain and allows one retry on the same profile with `ANTHROPIC_*` from the local Claude `SECRET.md` only after quota, limit, or reset errors; `externalClaudeSecretMode: force` applies the same environment override to the primary Claude call.

If your environment differs, update the invocation commands in the installed `skills/consultant/SKILL.md` under "Execution paths".

### Temporary files

The installed `AGENTS.md` refers to "the designated local temp area" for scratch files. Configure this per your project's conventions (e.g., a gitignored `.scratch/` directory, a RAM disk, or your OS temp folder).

## Uninstall

### Repo-level
```bash
rm -rf .agents/
# Remove the Orchestrarium section from AGENTS.md manually
```

### Global
```bash
rm -rf ~/.codex/skills/
# Remove the Orchestrarium section from ~/.codex/AGENTS.md manually
```
