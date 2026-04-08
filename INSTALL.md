# Installation

This repo contains the Orchestrarium skill-pack source in `src.codex/`. Install scripts copy it into the target `.codex/` directory. Installing into another machine or repository means running `install.ps1` or `install.sh`.

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

The scripts handle clean removal of old files, copying, AGENTS.md merging, and file-level verification. Re-running = reinstall. Policies are preserved across reinstalls.

## Install into a target repository

### What to copy

| Source | Destination | Purpose |
| --- | --- | --- |
| `src.codex/skills/` (31 roles) | `.codex/skills/` | Role definitions with `SKILL.md` and `agents/openai.yaml` |
| `src.codex/common-skills/` | `.codex/common-skills/` | Utility skills (`ask-claude`, `second-opinion`) |
| `src.codex/scripts/` | `.codex/scripts/` | Publication safety scan, validation |
| `src.codex/AGENTS.md` | Merge into target `.codex/AGENTS.md` | Governance: delegation, hygiene, publication safety, role index |

### Optional

| Source | Destination | Purpose |
| --- | --- | --- |
| `src.codex/policies/` | `.codex/policies/` | Policy catalog template (not overwritten on reinstall) |

### What NOT to copy

| Path | Why |
| --- | --- |
| `references/` | Skill-pack internal reference docs, not needed at runtime |
| `work-items/` | This repo's task memory — target repo has its own |
| `README.md`, `LICENSE`, `INSTALL.md` | Repo metadata |

### Steps

1. Copy `src.codex/skills/`, `src.codex/common-skills/`, `src.codex/scripts/` into target repo's `.codex/`
2. Merge `src.codex/AGENTS.md` content at the TOP of target's `.codex/AGENTS.md` (prepend). Original user content stays below intact.
3. Optionally copy `src.codex/policies/`
4. Restart Codex

## File separation

| Directory | Contents | Installable? |
| --- | --- | --- |
| `src.codex/skills/<role>/SKILL.md` | 31 role definitions | Yes |
| `src.codex/skills/<role>/agents/openai.yaml` | Display metadata and default prompt for the role | Yes |
| `src.codex/skills/lead/` | Operating-model notes, handoff contracts | Yes |
| `src.codex/skills/consultant/` | Consultant workflow, toggle logic, execution paths | Yes |
| `src.codex/common-skills/ask-claude/` | Claude CLI invocation skill | Yes |
| `src.codex/common-skills/second-opinion/` | Consultant toggle and explicit invocation | Yes |
| `src.codex/scripts/` | Publication safety scan, validation | Yes |
| `src.codex/policies/` | Policy catalog template (copy and customize) | Optional |
| `src.codex/AGENTS.md` | Governance: delegation, hygiene, publication safety, role index | Yes |
| `references/` | Full reference docs (diagrams, translations, strategy) | No — skill-pack internal |
| `work-items/` | This repo's task memory | No — skill-pack internal |

## Post-install

The pack is self-contained. No files from this development repository's root are needed at runtime.

### Repo-local customization

Add a project-level `AGENTS.md` at your project root (outside `.codex/`) for project-specific rules:

- canonical paths and source-of-truth references
- allowed toolchains, shells, build systems, and concrete build/test commands
- API, config, schema, and migration evolution rules
- rollback expectations, rollout rules, and project-specific budgets or SLAs
- repository-specific portability assumptions
- task-memory root location (e.g., `work-items/`) and recovery policy

The installed `.codex/AGENTS.md` covers global delegation, engineering hygiene, and role definitions. Your project-level `AGENTS.md` extends it with local context.

## Portability

### Claude CLI invocation

The `ask-claude` common skill and `consultant/SKILL.md` include invocation examples for both macOS/Linux and Windows.

- **macOS / Linux**: uses `claude` directly.
- **Windows**: uses `cmd.exe /c claude.exe` (or `claude.cmd` as fallback) to work inside Git Bash environments where Codex typically runs.

If your environment differs, update the invocation commands in `.codex/common-skills/ask-claude/invocation.md`.

### Temporary files

The installed `AGENTS.md` refers to "the designated local temp area" for scratch files. Configure this per your project's conventions (e.g., a gitignored `.scratch/` directory, a RAM disk, or your OS temp folder).

## Uninstall

Remove the `.codex/` folder from your project:

```bash
rm -rf your-project/.codex/
```
