# Installation

This repo contains the Orchestrarium skill-pack source in `src.codex/`. Install scripts copy it into the correct target locations. The target structure depends on the install mode.

## Quick install — current machine (global)

```powershell
# PowerShell (Windows)
.\install.ps1 -Global
```

```bash
# Bash (macOS / Linux / Git Bash)
bash install.sh --global
```

Global install copies everything into `~/.codex/` (mirrors `src.codex/` structure).

## Install into a specific repo

```powershell
.\install.ps1 -Target "D:\my-repo"
```

```bash
bash install.sh --target /path/to/repo
```

Repo-level install places skills into `.agents/skills/`, merges `AGENTS.md` into the project root, and keeps consultant toggle state in `.agents/.consultant-mode`.

## Install into current repo (default)

```powershell
.\install.ps1
```

```bash
bash install.sh
```

## Install target mapping

| Source | Global (`--global`) | Repo-level (default / `--target`) |
| --- | --- | --- |
| `src.codex/skills/` | `~/.codex/skills/` | `.agents/skills/` |
| `src.codex/skills/lead/scripts/` | `~/.codex/skills/lead/scripts/` | `.agents/skills/lead/scripts/` |
| `src.codex/AGENTS.md` | Merge into `~/.codex/AGENTS.md` | Merge into root `AGENTS.md` |

The scripts handle clean removal of old files, copying, AGENTS.md merging, and file-level verification. Re-running = reinstall.

Second-opinion toggle state is always project-local at `.agents/.consultant-mode`, even when the skill pack itself is installed globally.

Project policies are configured as a `## Project policies` section in the target `AGENTS.md`, not as a separate directory. See `skills/lead/policies-catalog.md` for available policy options.

## File separation

| Directory | Contents | Installable? |
| --- | --- | --- |
| `src.codex/skills/<role>/SKILL.md` | 31 role definitions + 1 utility skill | Yes |
| `src.codex/skills/<role>/agents/openai.yaml` | Display metadata and default prompt | Yes |
| `src.codex/skills/lead/` | Operating-model notes, handoff contracts | Yes |
| `src.codex/skills/consultant/` | Consultant role: toggle logic, execution paths, inline Claude CLI invocation | Yes |
| `src.codex/skills/second-opinion/` | Consultant toggle and explicit invocation | Yes |
| `src.codex/skills/lead/scripts/` | Publication safety scan, validation | Yes |
| `src.codex/skills/lead/policies-catalog.md` | Policy options reference (installed with skills) | Yes |
| `src.codex/AGENTS.md` | Governance: delegation, hygiene, publication safety, role index | Yes |
| `references/` | Full reference docs (diagrams, translations, strategy) | No — skill-pack internal |

## Post-install

The pack is self-contained. No files from this development repository's root are needed at runtime.

### Repo-local customization

Add project-specific rules to your root `AGENTS.md` (below the installed Orchestrarium section):

- canonical paths and source-of-truth references
- allowed toolchains, shells, build systems, and concrete build/test commands
- API, config, schema, and migration evolution rules
- rollback expectations, rollout rules, and project-specific budgets or SLAs
- repository-specific portability assumptions
- configured task-memory directory and recovery policy

The installed `AGENTS.md` covers global delegation, engineering hygiene, and role definitions. Your project-level additions extend it with local context.

## Portability

### Claude CLI invocation

`consultant/SKILL.md` includes Claude CLI invocation examples for both macOS/Linux and Windows.

- **macOS / Linux**: uses `claude` directly.
- **Windows**: uses `cmd.exe /c claude.exe` (or `claude.cmd` as fallback) to work inside Git Bash environments where Codex typically runs.

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
