# Installation

This monorepo ships two pack-specific installers plus two root router installers. The root `install.sh` and `install.ps1` scripts prompt for Codex, Claude Code, or both, then forward the same arguments unchanged to the matching pack-specific installers.

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
  1) Codex (Orchestrarium)
  2) Claude Code (Claudestrator)
  3) Both
```

For `Both`, the router reuses the same forwarded arguments for both pack-specific installers.

## Codex install details

Use `install-codex.sh` or `install-codex.ps1` when you want the Codex pack directly.

| Command | Result |
| --- | --- |
| `bash install-codex.sh --global` | Installs into `~/.codex/` |
| `bash install-codex.sh --target /path/to/project` | Installs into the target project's `.agents/skills/` and merges root `AGENTS.md` |
| `.\install-codex.ps1 -Global` | Installs into `~/.codex/` |
| `.\install-codex.ps1 -Target "D:\path\to\project"` | Installs into the target project's `.agents/skills/` and merges root `AGENTS.md` |

Notes:

- Project-level Codex installs use `.agents/skills/` plus the project root `AGENTS.md`.
- The second-opinion toggle remains project-local at `.agents/.consultant-mode`.
- Validation command: `bash src.codex/skills/lead/scripts/validate-skill-pack.sh`.

## Claude Code install details

Use `install-claude.sh` or `install-claude.ps1` when you want the Claude Code pack directly.

| Command | Result |
| --- | --- |
| `bash install-claude.sh --global` | Installs into `~/.claude/` |
| `bash install-claude.sh --target /path/to/project` | Installs into the target project's `.claude/` |
| `.\install-claude.ps1 -Global` | Installs into `~/.claude/` |
| `.\install-claude.ps1 -Target "D:\path\to\project"` | Installs into the target project's `.claude/` |

Notes:

- Project-level Claude installs create or update `.claude/AGENTS.md` and `.claude/CLAUDE.md`.
- Claude memory is shipped in `src.claude/memory/` and preserved across reinstalls by the existing installer behavior.
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

- `references-codex/`
- `references-claude/`

## Post-install customization

Customize each platform in the place that platform actually reads:

- Codex: append project-specific rules below the installed section in the project root `AGENTS.md`.
- Claude Code: append project-specific rules below the installed section in `.claude/CLAUDE.md`.

When both packs are installed, keep shared project policies aligned across both files. The repository's dev overlays, `AGENTS.md` and `CLAUDE.md`, are for maintaining this monorepo and are not copied into target projects by the install scripts.
