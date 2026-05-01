# Orchestrarium Codex

A standalone Codex production pack built on Codex-native runtime surfaces plus the Orchestrarium shared role principle.

Codex is one of the production-recommended Orchestrarium provider lines. Production `externalProvider: auto` routing stays on `codex | claude`; Gemini and Qwen remain explicit example-only integrations outside this branch.

This branch intentionally keeps only the Codex pack, its Codex references, and the shared governance files required for Codex installation and validation. It does not carry the Claude, Gemini, or Qwen source trees.

The full monorepo root installer uses Codex plus Claude as the default production install. Pressing Enter selects the default production install there. This standalone Codex branch exposes only the explicit Codex installer.

## Repository Layout

```text
scripts/install-codex.ps1         Windows installer
scripts/install-codex.sh          POSIX installer
references-codex/                 Codex-side maintainer references and compatibility pointers
shared/                           Shared governance and operator defaults required by Codex install
src.codex/                        Codex pack source tree
  AGENTS.codex.md                 Codex platform rules merged with shared governance
  agents/*.toml                   Built-in Codex agent override payloads
  skills/<name>/SKILL.md          Codex skills
  skills/<name>/agents/openai.yaml
                                   Role metadata and prompt overlays
  skills/lead/                    Lead operating model, contracts, and validators
docs/                             Branch-local operator and runtime docs
INSTALL.md                        Installation and usage notes
LICENSE                           Mozilla Public License 2.0
```

## Current Scope

- Ships Codex-native project-local and global installers.
- Keeps the full Codex-line role surface for production use.
- Uses `shared/AGENTS.shared.md` plus `src.codex/AGENTS.codex.md` to assemble installed `AGENTS.md`.
- Seeds `.agents/.agents-mode.yaml` as the Orchestrarium routing overlay.
- Seeds built-in Codex custom-agent overrides into `.codex/agents/` for project installs or `~/.codex/agents/` for global installs.

## Codex Bootstrap Model

1. Install the pack with `scripts/install-codex.ps1` or `scripts/install-codex.sh`.
2. For project installs, the installer materializes root `AGENTS.md`, `.agents/skills/`, `.agents/.agents-mode.yaml`, and `.codex/agents/`.
3. For global installs, the installer materializes `~/.codex/AGENTS.md`, `~/.codex/skills/`, `~/.codex/.agents-mode.yaml`, and `~/.codex/agents/`.
4. Run `$init-project` after first project install to configure project policies and review or update `.agents/.agents-mode.yaml`.
5. Treat legacy extensionless `.agents-mode` files as compatibility input only; normalize them forward into `.agents-mode.yaml`.

## Validation

```bash
bash src.codex/skills/lead/scripts/validate-skill-pack.sh
```

```powershell
.\src.codex\skills\lead\scripts\validate-skill-pack.ps1
```

Branch-local docs start at [docs/README.md](docs/README.md).

## Terms and Abbreviations

- `AGENTS.md`: Codex-readable governance file assembled from shared and Codex-specific sources.
- `agents-mode`: Orchestrarium routing overlay for provider preferences and execution policy.
- `CLI`: Command-Line Interface; a terminal command surface.
- `Codex`: OpenAI Codex runtime and production-recommended provider line.
- `Claude`: Anthropic Claude runtime and production-recommended provider line.
- `Gemini`: Google Gemini provider line, kept outside production auto routing.
- `Qwen`: Qwen provider line, kept outside production auto routing.
- `runtime`: installed provider-facing files used by Codex outside the source tree.
- `TOML`: Tom's Obvious Minimal Language, the configuration format used by Codex agent override files.
- `YAML`: YAML Ain't Markup Language, the configuration format used by `.agents-mode.yaml`.
