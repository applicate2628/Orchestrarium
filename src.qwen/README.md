# Orchestrarium Qwen

A standalone Qwen Code example pack built on Qwen-native runtime surfaces plus the full Orchestrarium shared role principle.

This pack remains installable and inspectable, but the repository classifies Qwen as `WEAK MODEL / NOT RECOMMENDED`. Production `externalProvider: auto` routing stays on `codex | claude`; explicit Qwen routes are manual example or compatibility paths only.

This branch keeps only Qwen-specific source, but it ships the same full role vocabulary as the neighboring packs:

- Qwen owns `QWEN.md` through the Qwen `/init` flow.
- Orchestrarium keeps one source-side shared-governance module in `src.qwen/AGENTS.shared.md`, which installers materialize as runtime `AGENTS.md`.
- Qwen runtime config stays in `.qwen/settings.json`.
- Orchestrarium seeds `.qwen/.agents-mode.yaml` as the shared routing overlay for named priority profiles and per-lane opinion counts.
- Stable expertise lives in `src.qwen/skills/`.
- Bounded parallel external-helper orchestration lives in `src.qwen/skills/external-brigade/` and the Qwen command wrapper under `commands/agents/external-brigade.md`.
- Specialist-team execution lives in `src.qwen/agents/`.
- Every markdown file directly under `src.qwen/agents/` must be a real Qwen agent definition with YAML frontmatter; explanatory docs stay outside that loader-visible path.

## Repository Layout

```text
install-qwen.ps1            Windows installer
install-qwen.sh             POSIX installer
references-qwen/            Required Qwen-side maintainer references
src.qwen/                   Qwen pack source tree
  QWEN.md                   Native Qwen entrypoint
  AGENTS.shared.md          Source-side shared-governance module for installed AGENTS.md
  skills/<name>/SKILL.md    Qwen skills
  agents/*.md               Qwen specialist subagents only
  agents/team-templates/    Repo-local team compositions
  commands/**/*.md          Qwen custom commands
  extension/                Extension manifest source for the installed Qwen extension package
  scripts/validate-pack.sh  Standalone pack validation (bash)
  scripts/validate-pack.ps1 Standalone pack validation (PowerShell)
docs/agents-mode-reference.md
                            Canonical reference for the installed Orchestrarium
                            `.qwen/.agents-mode.yaml` overlay
docs/provider-runtime-layouts.md
                            Source-vs-installed Qwen surface map
INSTALL.md                  Installation and usage notes for this monorepo
LICENSE                     Apache License 2.0
```

## Current Scope

This branch is a standalone Qwen example pack with a full Qwen-line role surface.

- It ships Qwen-native installers for project-local and global installs.
- It carries one required provider-local reference tree: `references-qwen/`.
- It does not promote Qwen into production `auto` routing.
- It keeps Qwen installable for example, compatibility, and inspection use without presenting Qwen as a production-recommended auto-routing target.
- It keeps command payloads in Markdown, matching the Qwen line, while Gemini keeps TOML command payloads.

## Qwen Bootstrap Model

1. Install the pack with `scripts/install-qwen.ps1` or `scripts/install-qwen.sh`.
2. If the target repository already has a user-owned `QWEN.md`, the installer preserves it and prepends only the managed Orchestrarium pack block.
3. Run Qwen's `/init` when you want Qwen to refresh or extend the user-owned portion of `QWEN.md`.
4. Use the installed extension payload under `.qwen/extensions/orchestrarium-qwen/` for the full shared role principle, including `external-brigade` when one bounded batch needs multiple parallel external helpers.
5. Keep top-level `.qwen/skills/`, `.qwen/agents/`, and `.qwen/commands/` free for deliberate user overrides instead of mirroring the same Orchestrarium pack there.
6. Use the Orchestrarium Qwen `init-project` helper to review or update the installed default `.qwen/.agents-mode.yaml` overlay after `/init`.
7. Keep `.qwen/settings.json` and extension manifests as the Qwen-native MCP and runtime-config surface.

The overlay reference in [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) also records task continuity, continue-by-default execution expectations, and the named production priority profiles used for multi-opinion routing.

## Validation

```bash
bash src.qwen/scripts/validate-pack.sh .
```

```powershell
.\src.qwen\scripts\validate-pack.ps1
```

Branch-local docs start at [../docs/README.md](../docs/README.md).

## License

This repository is licensed under the Apache License 2.0. See [../LICENSE](../LICENSE).
