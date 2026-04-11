# Orchestrarium Gemini

A standalone Gemini CLI provider pack built around the official Gemini runtime model plus the full Orchestrarium shared role principle.

This branch keeps only Gemini-specific source, but it now ships the same full role vocabulary as the neighboring packs:

- Gemini owns `GEMINI.md` through the built-in `/init` flow.
- Orchestrarium keeps one source-side shared-governance module in `src.gemini/AGENTS.shared.md`, which installers materialize as runtime `AGENTS.md`.
- Gemini runtime config stays in `.gemini/settings.json`.
- Orchestrarium adds an optional `.gemini/.agents-mode` overlay for shared routing semantics, named priority profiles, and per-lane opinion counts.
- Stable expertise lives in `src.gemini/skills/`.
- Preview specialist-team execution lives in `src.gemini/agents/`.
- Bounded parallel external-helper orchestration lives in `src.gemini/skills/external-brigade/` and `src.gemini/commands/agents/external-brigade.toml`.

## Repository layout

```text
install-gemini.ps1          Windows installer
install-gemini.sh           POSIX installer
references-gemini/          Required Gemini-side maintainer references
src.gemini/                 Gemini pack source tree
  GEMINI.md                 Native Gemini entrypoint
  AGENTS.shared.md          Source-side shared-governance module for installed AGENTS.md
  skills/<name>/SKILL.md    Gemini Agent Skills
  agents/*.md               Gemini preview specialist subagents
  agents/team-templates/    Repo-local team compositions
  commands/**/*.toml        Gemini custom commands
  extension/                Future extension and MCP boundary
  scripts/validate-pack.sh  Standalone pack validation (bash)
  scripts/validate-pack.ps1 Standalone pack validation (PowerShell)
docs/agents-mode-reference.md
                            Canonical reference for the optional Orchestrarium
                            `.gemini/.agents-mode` overlay
docs/provider-runtime-layout.md
                            Source-vs-installed Gemini surface map
INSTALL.md                  Installation and usage notes for this standalone branch
LICENSE                     Apache License 2.0
```

## Current scope

This branch is a standalone Gemini pack with a full Gemini-line role surface.

- It ships Gemini-native installers for project-local and global installs.
- It carries one required provider-local reference tree: `references-gemini/`.
- It does not carry Codex or Claude provider trees.
- It does not carry shared monorepo reference trees or cross-provider maintenance overlays.

## Gemini bootstrap model

1. Install the pack with `install-gemini.ps1` or `install-gemini.sh`.
2. If the target repository already has a user-owned `GEMINI.md`, the installer preserves it and prepends only the managed Orchestrarium pack block.
3. Run Gemini's built-in `/init` when you want Gemini to refresh or extend the user-owned portion of `GEMINI.md`.
4. Use the installed `.gemini/skills/` and `.gemini/agents/` layers for the full shared role principle.
5. Use the Orchestrarium Gemini `init-project` helper only if you also want the optional `.gemini/.agents-mode` overlay.
6. Use `external-brigade` when one bounded batch needs multiple parallel external helpers instead of trying to squeeze that through `externalOpinionCounts`.

The overlay reference in [docs/agents-mode-reference.md](docs/agents-mode-reference.md) also records task continuity, continue-by-default execution expectations, and the named priority profiles used for multi-opinion routing for initialized projects.
7. Keep `.gemini/settings.json` and extension manifests as the Gemini-native MCP and runtime-config surface; servers such as Serena, Fetch, or Context7 belong there, not in installed `AGENTS.md`.

## Validation

```bash
bash src.gemini/scripts/validate-pack.sh .
```

```powershell
.\src.gemini\scripts\validate-pack.ps1
```

Branch-local docs start at [docs/README.md](docs/README.md).

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
