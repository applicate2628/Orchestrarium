# Orchestrarium Gemini

A standalone Gemini CLI example pack built around the official Gemini runtime model plus the full Orchestrarium shared role principle.

This pack remains installable and inspectable, but the repository classifies Gemini as `WEAK MODEL / NOT RECOMMENDED`. Production `externalProvider: auto` routing stays on `codex | claude`; explicit Gemini routes are manual example or compatibility paths only.

This branch keeps only Gemini-specific source, but it now ships the same full role vocabulary as the neighboring packs:

- Gemini owns `GEMINI.md` through the built-in `/init` flow.
- Orchestrarium keeps one shared-governance source in `shared/AGENTS.shared.md`, which `src.gemini/GEMINI.md` imports in the monorepo and installers materialize as runtime `AGENTS.md`.
- Gemini runtime config stays in `.gemini/settings.json`.
- Orchestrarium seeds `.gemini/.agents-mode.yaml` as the shared routing overlay for named priority profiles and per-lane opinion counts.
- Stable expertise lives in `src.gemini/skills/`.
- Bounded parallel external-helper orchestration lives in `src.gemini/skills/external-brigade/` and the Gemini command wrapper under `commands/agents/external-brigade.toml`.
- Preview specialist-team execution lives in `src.gemini/agents/`.
- Every markdown file directly under `src.gemini/agents/` must be a real Gemini agent definition with YAML frontmatter; explanatory docs stay outside that loader-visible path.

## Repository layout

```text
scripts/install-gemini.ps1  Windows installer
scripts/install-gemini.sh   POSIX installer
references-gemini/          Required Gemini-side maintainer references
src.gemini/                 Gemini pack source tree
  GEMINI.md                 Native Gemini entrypoint
  skills/<name>/SKILL.md    Gemini Agent Skills
  agents/*.md               Gemini preview specialist subagents only
  agents/team-templates/    Repo-local team compositions
  commands/**/*.toml        Gemini custom commands
  extension/                Extension manifest source for the installed Gemini extension package
  scripts/validate-pack.sh  Standalone pack validation (bash)
  scripts/validate-pack.ps1 Standalone pack validation (PowerShell)
docs/agents-mode-reference.md
                            Canonical reference for the installed Orchestrarium
                            `.gemini/.agents-mode.yaml` overlay
docs/provider-runtime-layouts.md
                            Source-vs-installed Gemini surface map
shared/AGENTS.shared.md     Canonical shared governance source for installed AGENTS.md
INSTALL.md                  Installation and usage notes for this standalone branch
LICENSE                     Mozilla Public License 2.0
```

## Current scope

This branch is a standalone Gemini example pack with a full Gemini-line role surface.

- It ships Gemini-native installers for project-local and global installs.
- It carries one required provider-local reference tree: `references-gemini/`.
- It does not carry Codex or Claude provider trees.
- It does not carry shared monorepo reference trees or cross-provider maintenance overlays.
- It keeps Gemini installable for example, compatibility, and inspection use without presenting Gemini as a production-recommended auto-routing target.

## Gemini bootstrap model

1. Install the pack with `install-gemini.ps1` or `install-gemini.sh`.
2. If the target repository already has a user-owned `GEMINI.md`, the installer preserves it and prepends only the managed Orchestrarium pack block.
3. Run Gemini's built-in `/init` when you want Gemini to refresh or extend the user-owned portion of `GEMINI.md`.
4. Use the installed extension payload under `.gemini/extensions/orchestrarium-gemini/` for the full shared role principle, including `external-brigade` when one bounded batch needs multiple parallel external helpers.
5. Keep top-level `.gemini/skills/`, `.gemini/agents/`, and `.gemini/commands/` free for deliberate user overrides instead of mirroring the same Orchestrarium pack there, because Gemini gives those tiers precedence over extension content.
6. Use the Orchestrarium Gemini `init-project` helper to review or update the installed default `.gemini/.agents-mode.yaml` overlay after `/init`.

The overlay reference in [../docs/agents-mode-reference.md](../docs/agents-mode-reference.md) also records task continuity, continue-by-default execution expectations, and the named priority profiles used for multi-opinion routing.
7. Keep `.gemini/settings.json` and extension manifests as the Gemini-native MCP and runtime-config surface; servers such as Serena, Fetch, or Context7 belong there, not in installed `AGENTS.md`.

## Validation

```bash
bash src.gemini/scripts/validate-pack.sh .
```

```powershell
.\src.gemini\scripts\validate-pack.ps1
```

Branch-local docs start at [../docs/README.md](../docs/README.md).

## License

This repository is licensed under the Mozilla Public License 2.0. See [../LICENSE](../LICENSE).

## Terms and Abbreviations

- `AGENTS.md`: Orchestrarium shared-governance module materialized for Gemini installs and imported by `GEMINI.md`.
- `agents-mode`: Orchestrarium routing overlay for provider preferences and execution policy.
- `CLI`: Command-Line Interface, the terminal runtime surface for Gemini.
- `Gemini`: Google Gemini CLI provider line, kept here as an explicit example integration.
- `MCP`: Model Context Protocol; runtime mechanism for tool and resource servers.
- `runtime`: installed provider-facing files used by Gemini outside the source tree.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for Gemini as example-only and excluded from production defaults.
- `YAML`: YAML Ain't Markup Language, the frontmatter and configuration format used by several pack files.
