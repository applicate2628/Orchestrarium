# Orchestrarium Qwen

A standalone Qwen Code example pack built on Qwen-native runtime surfaces plus the full Orchestrarium shared role principle.

Qwen is maintained here as an installable and inspectable example integration, but it is classified as `WEAK MODEL / NOT RECOMMENDED`. Production `externalProvider: auto` routing stays on `codex | claude`; explicit Qwen routes are manual example or compatibility paths only.

This branch intentionally keeps only the Qwen pack, its Qwen references, and the shared governance files required for Qwen installation and validation. It does not carry the Codex, Claude, or Gemini source trees.

## Repository Layout

```text
scripts/install-qwen.ps1    Windows installer
scripts/install-qwen.sh     POSIX installer
references-qwen/            Qwen-side maintainer references and compatibility pointers
shared/                     Shared governance and operator defaults required by Qwen install
src.qwen/                   Qwen pack source tree
  QWEN.md                   Native Qwen entrypoint template
  skills/<name>/SKILL.md    Qwen skills
  agents/*.md               Qwen specialist subagents only
  agents/team-templates/    Repo-local team compositions
  commands/**/*.md          Qwen custom commands
  extension/                Installed extension manifest source
  scripts/validate-pack.*   Standalone pack validation
docs/                       Branch-local operator and runtime docs
INSTALL.md                  Installation and usage notes
LICENSE                     Mozilla Public License 2.0
```

## Current Scope

- Ships Qwen-native project-local and global installers.
- Keeps a full Qwen-line role surface for example, compatibility, and inspection use.
- Keeps Qwen out of production `auto` routing.
- Keeps command payloads in Markdown, matching the Qwen line.

## Qwen Bootstrap Model

1. Install the pack with `scripts/install-qwen.ps1` or `scripts/install-qwen.sh`.
2. If the target repository already has a user-owned `QWEN.md`, the installer preserves it and prepends only the managed Orchestrarium pack block.
3. Run Qwen `/init` when you want Qwen to refresh or extend the user-owned portion of `QWEN.md`.
4. Use the installed extension payload under `.qwen/extensions/orchestrarium-qwen/` for the full shared role principle.
5. Use `.qwen/.agents-mode.yaml` as the Orchestrarium routing overlay; `.qwen/settings.json` remains the Qwen-native runtime config surface.

## Validation

```bash
bash src.qwen/scripts/validate-pack.sh .
```

```powershell
.\src.qwen\scripts\validate-pack.ps1
```

Branch-local docs start at [docs/README.md](docs/README.md).

## Terms and Abbreviations

- `AGENTS.md`: Orchestrarium shared-governance file materialized for Qwen installs.
- `agents-mode`: Orchestrarium routing overlay for provider preferences and execution policy.
- `MCP`: Model Context Protocol; runtime mechanism for tool and resource servers.
- `Qwen`: Qwen provider line, kept here as an explicit example integration.
- `runtime`: installed provider-facing files used by Qwen outside the source tree.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for Qwen as example-only and excluded from production defaults.
- `YAML`: YAML Ain't Markup Language, the frontmatter and configuration format used by several pack files.
