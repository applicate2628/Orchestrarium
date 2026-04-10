@../shared/AGENTS.shared.md

# Gemini Provider Pack

This file is the Gemini-native runtime entrypoint for the Orchestrarium Gemini pack scaffold.

Use this pack as a minimal Gemini-native scaffold built on official runtime surfaces:

- `GEMINI.md` is the native runtime instruction file.
- `skills/` contains Gemini-native Agent Skills with `SKILL.md` entrypoints.
- `commands/` contains Gemini-native TOML custom commands.
- `extension/` is reserved for Gemini-native MCP and tools packaging.

This scaffold intentionally stays lean and official-preferred:

- shared governance is imported directly from `../shared/AGENTS.shared.md` through standard `GEMINI.md` imports
- the expertise layer is modeled as Gemini skills, not a custom `agents/` tree
- commands stay user-invoked TOML shortcuts rather than pretending to be skills
- pack growth should stay inside official Gemini surfaces first, then add repo-local layers only when a real runtime need appears
