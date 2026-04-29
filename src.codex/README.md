# Codex Pack Source

This directory contains the Codex-provider source tree inside the Orchestrarium monorepo.

Use it together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs surface
- [../shared/references/README.md](../shared/references/README.md) for the shared design core
- [../references-codex/README.md](../references-codex/README.md) for the Codex-side provider addendum

Source surface:

- `../shared/AGENTS.shared.md` + `AGENTS.codex.md` assemble the installed Codex `AGENTS.md`
- `agents/default.toml`, `agents/worker.toml`, and `agents/explorer.toml` seed the Codex built-in custom-agent overrides installed under `.codex/agents/`
- `skills/<role>/SKILL.md` and `skills/<role>/agents/openai.yaml` define the role catalog
- `skills/lead/` carries operating-model notes, handoff contracts, and validation/publication-safety scripts
- `skills/consultant/` and `skills/second-opinion/` carry the advisory and explicit consultant routing surfaces
- `skills/external-brigade/` carries the bounded parallel external-helper orchestration surface

Keep `SKILL.md` frontmatter `description:` values compact because Codex loads them as startup metadata before any one skill body is selected. Put detailed trigger logic, scope, and gate rules in the body of the skill instead; `skills/lead/scripts/validate-skill-pack.*` enforces the Codex metadata budget.

This subtree is the Codex runtime source owned by the monorepo. Shared governance and shared references stay one level up; only the provider-specific runtime source lives here.
