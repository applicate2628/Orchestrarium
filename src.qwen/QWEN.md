<!-- ORCHESTRARIUM_QWEN_PACK:START -->
@./AGENTS.shared.md

# Qwen Provider Pack

This file is the Qwen-native runtime entrypoint template for the Orchestrarium Qwen example pack.

Use this pack as an example-only Qwen line built on official Qwen surfaces plus explicit Orchestrarium orchestration layers:

- `QWEN.md` is the native runtime instruction file.
- `Qwen Code /init` is the official way to create or refresh the project `QWEN.md`.
- `.qwen/settings.json` is the official Qwen runtime-state and configuration surface.
- Orchestrarium install seeds `.qwen/.agents-mode.yaml` as the shared-routing overlay with named priority profiles and per-lane opinion counts, and `init-project` reviews or updates that installed default.
- `skills/` carries the full stable Qwen skill catalog for the shared role vocabulary.
- `agents/` carries the Qwen specialist subagent layer for explicit delegation.
- `agents/team-templates/` carries the repo-local team compositions for the shared role principle.
- `commands/` carries Markdown-based Qwen custom commands.
- `extension/` keeps the manifest and extension-local docs that installers materialize into `.qwen/extensions/orchestrarium-qwen/` or `~/.qwen/extensions/orchestrarium-qwen/` for official Qwen extension loading and MCP.

Important distinctions:

- installers materialize the shared-governance layer as adjacent runtime `AGENTS.md`, and this file imports it through standard Qwen markdown imports
- the stable expertise layer is `skills/`
- the explicit specialist team layer is `agents/`
- every top-level `agents/*.md` file is loader-visible and must stay a real Qwen agent definition with YAML frontmatter; pack docs do not belong there
- Orchestrarium keeps orchestration in the main Qwen session under `skills/lead/SKILL.md` so stage ownership, accepted artifacts, and gate decisions stay explicit
- MCP servers such as Serena, Fetch, or Context7 remain a `.qwen/settings.json` or `qwen-extension.json` concern rather than a markdown-import concern
- `.qwen/.agents-mode.yaml` is an Orchestrarium routing overlay, not a replacement for official Qwen settings
- this repository classifies Qwen as `WEAK MODEL / NOT RECOMMENDED`; shipped `externalProvider: auto` profiles stay on `codex | claude` only
- explicit `externalProvider: qwen` is a manual example or compatibility path only, not a production recommendation
- decision-driving reads of `.qwen/.agents-mode.yaml` must normalize stale, comment-free, or older-layout overlays to the current canonical format before trusting flags
<!-- ORCHESTRARIUM_QWEN_PACK:END -->
