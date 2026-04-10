# Gemini Pack Source

This directory contains the source scaffold for the Orchestrarium Gemini provider pack.

The structure follows the official Gemini-preferred model instead of mirroring the Codex or Claude lines:

- `GEMINI.md` as the runtime entrypoint
- `skills/<name>/SKILL.md` for Gemini Agent Skills
- `commands/*.toml` for Gemini custom commands
- `extension/gemini-extension.json` for future MCP and tool packaging

This scaffold intentionally avoids extra repo-local runtime abstractions such as a Gemini-specific `agents/` tree or copied contract catalogs.

It does not yet include an installer or a full installed-runtime assembly flow.
