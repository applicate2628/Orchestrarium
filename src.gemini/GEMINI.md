<!-- ORCHESTRARIUM_GEMINI_PACK:START -->
# Gemini Provider Pack

This file is the Gemini-native runtime entrypoint for the Orchestrarium Gemini pack scaffold.

Use this pack as a minimal Gemini-native scaffold built on official runtime surfaces:

- `GEMINI.md` is the native runtime instruction file.
- Gemini CLI's built-in `/init` command is the official way to create or refresh the project `GEMINI.md`.
- `.gemini/settings.json` is the official Gemini runtime-state and configuration surface.
- Orchestrarium's `init-project` helper is the separate bootstrap path for `.gemini/.agents-mode` when shared routing toggles are needed.
- `skills/` contains Gemini-native Agent Skills with `SKILL.md` entrypoints.
- `commands/` contains Gemini-native TOML custom commands.
- `extension/` is reserved for Gemini-native MCP and tools packaging.

This scaffold intentionally stays lean and official-preferred:

- governance and runtime notes stay local to the Gemini scaffold instead of importing a shared monorepo layer
- the expertise layer is modeled as Gemini skills, not a custom `agents/` tree
- commands stay user-invoked TOML shortcuts rather than pretending to be skills
- Orchestrarium-specific cross-provider routing semantics, when needed, belong in `.gemini/.agents-mode` as a repo-local overlay rather than as a replacement for official Gemini settings
- use the Orchestrarium Gemini `init-project` helper only after the official `/init` has created or refreshed the project `GEMINI.md`
- pack growth should stay inside official Gemini surfaces first, then add repo-local layers only when a real runtime need appears
<!-- ORCHESTRARIUM_GEMINI_PACK:END -->
