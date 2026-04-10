# Gemini Pack Source

This directory contains the Gemini provider-pack source tree inside the Orchestrarium monorepo.

Use it together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs surface
- [../shared/references/README.md](../shared/references/README.md) for the shared design core
- [../references-gemini/README.md](../references-gemini/README.md) for the Gemini-side provider addendum

## Source shape

- `GEMINI.md` — Gemini-native runtime entrypoint template
- `AGENTS.shared.md` — source-side shared-governance module, materialized by installers as runtime `AGENTS.md`
- `skills/` — full stable Gemini skill catalog for the shared role vocabulary
- `agents/` — full Gemini preview specialist-team surface
- `agents/team-templates/` — repo-local orchestration templates for the shared role principle
- `commands/agents/*.toml` — Gemini command entrypoints
- `extension/gemini-extension.json` — extension-manifest boundary

## Contract

This pack no longer pretends to be a minimal Gemini-only scaffold.

It intentionally combines:

- official stable Gemini `skills/`
- official preview Gemini `agents/`
- repo-local team-template metadata

That combination is deliberate: all three Orchestrarium packs now carry the same role principle, while Gemini remains honest about which surfaces are official provider features and which surfaces are Orchestrarium orchestration metadata.

## Orchestration truth

- Gemini specialist subagents exist in `agents/`.
- The orchestration owner is still the main Gemini session under `skills/lead/SKILL.md`.
- Team-template execution happens in the main session because Gemini subagents cannot recursively call other subagents.
