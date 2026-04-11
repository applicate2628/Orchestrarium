# Gemini Extension Surface

This directory is the source-owned extension manifest surface for the installed Gemini package.

Gemini installers materialize it into `.gemini/extensions/orchestrarium-gemini/` for project installs and `~/.gemini/extensions/orchestrarium-gemini/` for global installs. The installed extension carries this manifest and README plus the mirrored Gemini runtime payload (`skills/`, `agents/`, `commands/`, `GEMINI.md`, and `AGENTS.md`).

Use it when the Gemini line needs:

- MCP servers
- Gemini-native tool registration
- extension-local runtime assets

The current `gemini-extension.json` is intentionally minimal, but it is now active install output rather than a source-only placeholder.
