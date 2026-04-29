# Gemini Extension Surface

This directory is the source-owned extension manifest surface for the installed Gemini example package.

Gemini installers materialize it into `.gemini/extensions/orchestrarium-gemini/` for project installs and `~/.gemini/extensions/orchestrarium-gemini/` for global installs. The installed extension carries this manifest and README plus the mirrored Gemini runtime payload (`skills/`, `agents/`, `commands/`, `GEMINI.md`, and `AGENTS.md`).

Gemini remains a `WEAK MODEL / NOT RECOMMENDED` example-only integration in this repository. Production `auto` routing stays on `codex | claude`; explicit Gemini routing is for manual example, compatibility, or inspection use only.

Use it when the Gemini example line needs:

- MCP servers
- Gemini-native tool registration
- extension-local runtime assets

The current `gemini-extension.json` is intentionally minimal, active install output, and explicitly example-only rather than a production-recommended routing surface.

## Terms and Abbreviations

- `AGENTS.md`: the installed governance file imported by the Gemini extension context.
- `GEMINI.md`: the Gemini-readable context file for a repository or extension.
- `MCP`: Model Context Protocol, a protocol used to expose tools and resources to agent runtimes.
- `WEAK MODEL / NOT RECOMMENDED`: the repository classification for example-only providers that must stay out of production `auto` routing.
