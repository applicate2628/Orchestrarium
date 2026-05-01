# Orchestrarium Gemini

A standalone Gemini CLI example pack built on Gemini-native runtime surfaces plus the Orchestrarium shared role principle.

Gemini is maintained here as an installable and inspectable example integration, but it is classified as `WEAK MODEL / NOT RECOMMENDED`. Production `externalProvider: auto` routing stays on `codex | claude`; explicit Gemini routes are manual example or compatibility paths only.

This branch intentionally keeps only the Gemini pack, its Gemini references, and the shared governance files required for Gemini installation and validation. It does not carry the Codex, Claude, or Qwen source trees.

The full monorepo root installer uses Codex plus Claude as the default production install. Pressing Enter selects the default production install there. This standalone Gemini branch exposes only the explicit Gemini example installer.

## Repository Layout

```text
scripts/install-gemini.ps1        Windows installer
scripts/install-gemini.sh         POSIX installer
references-gemini/                Gemini-side maintainer references and compatibility pointers
shared/                           Shared governance and operator defaults required by Gemini install
src.gemini/                       Gemini pack source tree
  GEMINI.md                       Native Gemini entrypoint template
  skills/<name>/SKILL.md          Gemini skills
  agents/*.md                     Gemini preview specialist subagents
  agents/team-templates/          Repo-local team compositions
  commands/**/*.toml              Gemini custom commands
  extension/                      Installed extension manifest source
  scripts/validate-pack.*         Standalone pack validation
docs/                             Branch-local operator and runtime docs
INSTALL.md                        Installation and usage notes
LICENSE                           Mozilla Public License 2.0
```

## Current Scope

- Ships Gemini-native project-local and global installers.
- Keeps a full Gemini-line role surface for example, compatibility, and inspection use.
- Keeps Gemini out of production `auto` routing.
- Uses `shared/AGENTS.shared.md` as the canonical shared governance source.
- Installs the Gemini extension payload under `.gemini/extensions/orchestrarium-gemini/`.

## Gemini Bootstrap Model

1. Install the pack with `scripts/install-gemini.ps1` or `scripts/install-gemini.sh`.
2. If the target repository already has a user-owned `GEMINI.md`, the installer preserves it and prepends only the managed Orchestrarium pack block.
3. Run Gemini `/init` when you want Gemini to refresh or extend the user-owned portion of `GEMINI.md`.
4. Use the installed extension payload under `.gemini/extensions/orchestrarium-gemini/` for the full shared role principle.
5. Use `.gemini/.agents-mode.yaml` as the Orchestrarium routing overlay; `.gemini/settings.json` remains the Gemini-native runtime config surface.

## Validation

```bash
bash src.gemini/scripts/validate-pack.sh .
```

```powershell
.\src.gemini\scripts\validate-pack.ps1
```

Branch-local docs start at [docs/README.md](docs/README.md).

## Terms and Abbreviations

- `AGENTS.md`: Orchestrarium shared-governance file materialized for Gemini installs.
- `agents-mode`: Orchestrarium routing overlay for provider preferences and execution policy.
- `CLI`: Command-Line Interface; a terminal command surface.
- `Codex`: OpenAI Codex runtime and production-recommended provider line.
- `Claude`: Anthropic Claude runtime and production-recommended provider line.
- `Gemini`: Google Gemini provider line, kept here as an explicit example integration.
- `MCP`: Model Context Protocol; runtime mechanism for tool and resource servers.
- `Qwen`: Qwen provider line, kept outside production auto routing.
- `runtime`: installed provider-facing files used by Gemini outside the source tree.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for Gemini as example-only and excluded from production defaults.
- `YAML`: YAML Ain't Markup Language, the configuration format used by `.agents-mode.yaml`.
