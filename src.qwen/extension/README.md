# Qwen Extension Surface

This directory is the source-owned extension manifest surface for the installed Qwen example package.

Qwen installers materialize it into `.qwen/extensions/orchestrarium-qwen/` for project installs and `~/.qwen/extensions/orchestrarium-qwen/` for global installs. The installed extension carries this manifest and README plus the mirrored Qwen runtime payload (`skills/`, `agents/`, `commands/`, `QWEN.md`, and `AGENTS.md`).

Qwen remains a `WEAK MODEL / NOT RECOMMENDED` example-only integration in this repository. Production `auto` routing stays on `codex | claude`; explicit Qwen routing is for manual example, compatibility, or inspection use only.

Use it when the Qwen example line needs:

- MCP servers
- Qwen-native tool registration
- extension-local runtime assets

The current `qwen-extension.json` is intentionally minimal, active install output, and aligned with Qwen's native extension schema: context file, skills, agents, and commands all live in the extension payload.

## Terms and Abbreviations

- `AGENTS.md`: the installed governance file imported by the Qwen extension context.
- `MCP`: Model Context Protocol, a protocol used to expose tools and resources to agent runtimes.
- `QWEN.md`: the Qwen-readable context file for a repository or extension.
- `WEAK MODEL / NOT RECOMMENDED`: the repository classification for example-only providers that must stay out of production `auto` routing.
