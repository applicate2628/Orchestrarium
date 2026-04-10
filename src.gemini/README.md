# Gemini Pack Source

This directory contains the Gemini provider-pack source tree inside the Orchestrarium monorepo.

Use it together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs surface
- [../shared/references/README.md](../shared/references/README.md) for the shared design core
- [../references-gemini/README.md](../references-gemini/README.md) for the Gemini-side provider addendum

The structure follows the official Gemini-preferred model instead of mirroring the Codex or Claude lines:

- `GEMINI.md` as the runtime entrypoint
- Gemini CLI built-in `/init` as the official project bootstrap for `GEMINI.md`
- `.gemini/settings.json` as the official runtime-state and configuration surface
- `skills/init-project/SKILL.md` plus `commands/agents/init-project.toml` to bootstrap Orchestrarium's `.gemini/.agents-mode` overlay after the official `/init`
- `skills/<name>/SKILL.md` for Gemini Agent Skills
- `commands/*.toml` for Gemini custom commands
- `extension/gemini-extension.json` for future MCP and tool packaging

This source tree intentionally avoids extra repo-local runtime abstractions such as a Gemini-specific `agents/` tree or copied contract catalogs.

Inside the monorepo, this subtree carries the Gemini source surface and the shared-reference alignment work, not the standalone installer entrypoints. When Orchestrarium needs the same shared routing toggles used on the Codex and Claude lines, that provider-local overlay belongs in `.gemini/.agents-mode`; it complements official `.gemini/settings.json` instead of replacing it, and the local `init-project` helper exists to initialize that overlay after Gemini's built-in `/init`. When Gemini routes external work to Claude CLI, the same overlay may also carry `externalClaudeSecretMode: auto | force`.
