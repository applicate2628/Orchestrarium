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

This scaffold intentionally avoids extra repo-local runtime abstractions such as a Gemini-specific `agents/` tree.

The standalone branch still carries one required repo-local maintainer reference tree at `../references-gemini/`. That tree is source-branch documentation only; it is not part of the installed runtime payload.

The standalone branch now ships a Gemini-native install surface. Project installs place `GEMINI.md` at the project root and Gemini-native runtime assets under `.gemini/`; global installs place the same assets under `~/.gemini/`. When Orchestrarium needs the same shared routing toggles used on the Codex and Claude lines, that provider-local overlay belongs in `.gemini/.agents-mode`; it complements official `.gemini/settings.json` instead of replacing it, and the local `init-project` helper exists to initialize that overlay after Gemini's built-in `/init`. If Gemini routes external work to Claude CLI, that same overlay may also carry `externalClaudeSecretMode: auto | force`.
