# Orchestrarium Gemini

A standalone Gemini CLI provider-pack scaffold built around the official Gemini-preferred runtime model.

This branch intentionally keeps only Gemini-specific source and one small Orchestrarium overlay layer:

- Gemini owns `GEMINI.md` through the built-in `/init` flow.
- Gemini runtime config stays in `.gemini/settings.json`.
- Orchestrarium adds an optional `.gemini/.agents-mode` overlay only when shared routing toggles are needed.

## Repository layout

```text
install-gemini.ps1          Windows installer
install-gemini.sh           POSIX installer
references-gemini/          Required Gemini-side maintainer references
src.gemini/                 Gemini source scaffold
  GEMINI.md                 Native Gemini entrypoint
  skills/<name>/SKILL.md    Gemini Agent Skills
  commands/**/*.toml        Gemini custom commands
  extension/                Future extension and MCP boundary
  scripts/validate-pack.sh  Standalone scaffold validation
docs/agents-mode-reference.md
                            Canonical reference for the optional Orchestrarium
                            `.gemini/.agents-mode` overlay
docs/provider-runtime-layout.md
                            Source-vs-installed Gemini surface map
INSTALL.md                  Installation and usage notes for this standalone branch
LICENSE                     Apache License 2.0
```

## Current scope

This branch is a standalone Gemini pack with a lean official-preferred install surface.

- It ships Gemini-native installers for project-local and global installs.
- It carries one required provider-local reference tree: `references-gemini/`.
- It does not carry Codex or Claude provider trees.
- It does not carry shared monorepo reference trees or cross-provider maintenance overlays.

## Gemini bootstrap model

1. Install the pack with `install-gemini.ps1` or `install-gemini.sh`.
2. If the target repository already has a user-owned `GEMINI.md`, the installer preserves it and prepends only the managed Orchestrarium pack block.
3. Run Gemini's built-in `/init` when you want Gemini to refresh or extend the user-owned portion of `GEMINI.md`.
4. Use the Orchestrarium Gemini `init-project` helper only if you also want the optional `.gemini/.agents-mode` overlay.
5. Keep `.gemini/settings.json` as the Gemini-native runtime config surface.

## Validation

```bash
bash src.gemini/scripts/validate-pack.sh .
```

Branch-local docs start at [docs/README.md](docs/README.md).

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
