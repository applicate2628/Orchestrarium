<!-- ORCHESTRARIUM_GEMINI_PACK:START -->
@./AGENTS.shared.md

# Gemini Provider Pack

This file is the Gemini-native runtime entrypoint template for the Orchestrarium Gemini pack.

Use this pack as a full Gemini-line runtime surface built on official Gemini entrypoints plus explicit Orchestrarium orchestration layers:

- `GEMINI.md` is the native runtime instruction file.
- Gemini CLI `/init` is the official way to create or refresh the project `GEMINI.md`.
- `.gemini/settings.json` is the official Gemini runtime-state and configuration surface.
- Orchestrarium install seeds `.gemini/.agents-mode.yaml` as the shared-routing overlay with named priority profiles and per-lane opinion counts, and `init-project` reviews or updates that installed default.
- `skills/` carries the full stable Gemini skill catalog for the shared role vocabulary.
- `agents/` carries the Gemini preview specialist-team layer for explicit delegation.
- `agents/team-templates/` carries the repo-local team compositions for the shared role principle.
- `commands/` carries Gemini TOML command entrypoints.
- `extension/` keeps the manifest and extension-local docs that installers materialize into `.gemini/extensions/orchestrarium-gemini/` or `~/.gemini/extensions/orchestrarium-gemini/` for official Gemini extension loading and MCP.

Important distinctions:

- installers materialize the shared-governance layer as adjacent runtime `AGENTS.md`, and this file imports it through standard Gemini markdown imports
- the stable expertise layer is `skills/`
- the explicit specialist team layer is `agents/`
- every top-level `agents/*.md` file is loader-visible and must stay a real Gemini agent definition with YAML frontmatter; pack docs do not belong there
- orchestration stays in the main Gemini session under `skills/lead/SKILL.md` because Gemini subagents cannot recursively call other subagents
- MCP servers such as Serena, Fetch, or Context7 remain a `.gemini/settings.json` or `gemini-extension.json` concern rather than a markdown-import concern
- `.gemini/.agents-mode.yaml` is an Orchestrarium routing overlay, not a replacement for official Gemini settings
- decision-driving reads of `.gemini/.agents-mode.yaml` must normalize stale, comment-free, or older-layout overlays to the current canonical format before trusting flags
<!-- ORCHESTRARIUM_GEMINI_PACK:END -->
