# Gemini Pack Source

This directory contains the source scaffold for the Orchestrarium Gemini provider pack.

The structure follows the official Gemini-preferred model instead of mirroring the Codex or Claude lines:

- `GEMINI.md` as the runtime entrypoint
- Gemini CLI built-in `/init` as the official project bootstrap for `GEMINI.md`
- `.gemini/settings.json` as the official runtime-state and configuration surface
- `skills/init-project/SKILL.md` plus `commands/agents/init-project.toml` to bootstrap Orchestrarium's `.gemini/.agents-mode` overlay after the official `/init`
- `skills/<name>/SKILL.md` for Gemini Agent Skills
- `commands/*.toml` for Gemini custom commands
- `extension/gemini-extension.json` for future MCP and tool packaging

This scaffold intentionally avoids extra repo-local runtime abstractions such as a Gemini-specific `agents/` tree or copied contract catalogs.

It does not yet include an installer or a full installed-runtime assembly flow. When Orchestrarium needs the same shared routing toggles used on the Codex and Claude lines, that provider-local overlay belongs in `.gemini/.agents-mode`; it complements official `.gemini/settings.json` instead of replacing it, and the local `init-project` helper exists to initialize that overlay after Gemini's built-in `/init`.
