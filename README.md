# Claudestrator

A standalone Claude Code production pack built on Claude-native runtime surfaces plus the Orchestrarium shared role principle.

Claude is one of the production-recommended Orchestrarium provider lines. Production `externalProvider: auto` routing stays on `codex | claude`; Gemini and Qwen remain explicit example-only integrations outside this branch.

This branch intentionally keeps only the Claude pack, its Claude references, and the shared governance files required for Claude installation and validation. It does not carry the Codex, Gemini, or Qwen source trees.

The full monorepo root installer uses Codex plus Claude as the default production install. Pressing Enter selects the default production install there. This standalone Claude branch exposes only the explicit Claude installer.

## Repository Layout

```text
scripts/install-claude.ps1        Windows installer
scripts/install-claude.sh         POSIX installer
references-claude/                Claude-side maintainer references and compatibility pointers
shared/                           Shared governance and operator defaults required by Claude install
src.claude/                       Claude pack source tree
  CLAUDE.md                       Native Claude entrypoint template
  agents/<role>.md                Claude specialist subagents
  agents/contracts/               Handoff and dispatch contracts
  agents/team-templates/          Repo-local team compositions
  commands/agents-*.md            Claude slash commands
  skills/                         Claude skills and workflow helpers
  agents/scripts/validate-*       Standalone pack validation
docs/                             Branch-local operator and runtime docs
INSTALL.md                        Installation and usage notes
LICENSE                           Mozilla Public License 2.0
```

## Current Scope

- Ships Claude-native project-local and global installers.
- Keeps the full Claude-line role surface for production use.
- Uses `shared/AGENTS.shared.md` as the canonical shared governance source.
- Seeds `.claude/.agents-mode.yaml` as the Orchestrarium routing overlay.
- Keeps Claude-specific runtime config and guidance in the Claude pack only.

## Claude Bootstrap Model

1. Install the pack with `scripts/install-claude.ps1` or `scripts/install-claude.sh`.
2. If the target repository already has a user-owned `.claude/CLAUDE.md`, the installer preserves user content outside the managed Orchestrarium block.
3. Use `/agents-init-project` to configure project policies and review or update `.claude/.agents-mode.yaml`.
4. Keep `.claude/.agents-mode.yaml` as the Claude-line Orchestrarium routing overlay; legacy extensionless `.claude/.agents-mode` is compatibility input only.
5. Use the installed `.claude/agents/`, `.claude/commands/`, and `.claude/skills/` payload as the Claude-native role surface.

## Validation

```bash
bash src.claude/agents/scripts/validate-skill-pack.sh
```

```powershell
.\src.claude\agents\scripts\validate-skill-pack.ps1
```

Branch-local docs start at [docs/README.md](docs/README.md).

## Terms and Abbreviations

- `AGENTS.md`: Orchestrarium shared-governance file materialized for Claude installs.
- `agents-mode`: Orchestrarium routing overlay for provider preferences and execution policy.
- `CLI`: Command-Line Interface; a terminal command surface.
- `Codex`: OpenAI Codex runtime and production-recommended provider line.
- `Claude Code`: Anthropic Claude runtime and production-recommended provider line.
- `Gemini`: Google Gemini provider line, kept outside production auto routing.
- `Qwen`: Qwen provider line, kept outside production auto routing.
- `runtime`: installed provider-facing files used by Claude outside the source tree.
- `YAML`: YAML Ain't Markup Language, the configuration format used by `.agents-mode.yaml`.
