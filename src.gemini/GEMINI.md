<!-- ORCHESTRARIUM_GEMINI_PACK:START -->
@./AGENTS.shared.md

# Gemini Provider Pack

This file is the Gemini-native runtime entrypoint template for the Orchestrarium Gemini pack.

Use this pack as a full Gemini-line runtime surface built on official Gemini entrypoints plus explicit Orchestrarium orchestration layers:

- `GEMINI.md` is the native runtime instruction file.
- Gemini CLI `/init` is the official way to create or refresh the project `GEMINI.md`.
- `.gemini/settings.json` is the official Gemini runtime-state and configuration surface.
- Orchestrarium `init-project` bootstraps `.gemini/.agents-mode` as the shared-routing overlay with named priority profiles and per-lane opinion counts.
- `skills/` carries the full stable Gemini skill catalog for the shared role vocabulary.
- `agents/` carries the Gemini preview specialist-team layer for explicit delegation.
- `agents/team-templates/` carries the repo-local team compositions for the shared role principle.
- `commands/agents/external-brigade.toml` and `skills/external-brigade/SKILL.md` carry the bounded parallel external-helper orchestration surface.
- `commands/` carries Gemini TOML command entrypoints.
- `extension/` remains the extension-manifest boundary for Gemini-native packaging and MCP.

Important distinctions:

- installers materialize the shared-governance layer as adjacent runtime `AGENTS.md`, and this file imports it through standard Gemini markdown imports
- the stable expertise layer is `skills/`
- the explicit specialist team layer is `agents/`
- orchestration stays in the main Gemini session under `skills/lead/SKILL.md` because Gemini subagents cannot recursively call other subagents
- `external-brigade` is the bounded helper-batch utility when one request needs multiple parallel external helpers
- MCP servers such as Serena, Fetch, or Context7 remain a `.gemini/settings.json` or `gemini-extension.json` concern rather than a markdown-import concern
- `.gemini/.agents-mode` is an Orchestrarium routing overlay, not a replacement for official Gemini settings
- decision-driving reads of `.gemini/.agents-mode` must normalize stale, comment-free, or older-layout overlays to the current canonical format before trusting flags
<!-- ORCHESTRARIUM_GEMINI_PACK:END -->
