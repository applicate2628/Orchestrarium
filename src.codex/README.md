# Codex Pack Source

This directory contains the Codex-provider source tree inside the Orchestrarium monorepo.

Use it together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs surface
- [../shared/references/README.md](../shared/references/README.md) for the shared design core
- [../references-codex/README.md](../references-codex/README.md) for the Codex-side provider addendum

Source surface:

- `../shared/AGENTS.shared.md` + `AGENTS.codex.md` assemble the installed Codex `AGENTS.md`
- `skills/<role>/SKILL.md` and `skills/<role>/agents/openai.yaml` define the role catalog
- `skills/lead/` carries operating-model notes, handoff contracts, and validation/publication-safety scripts
- `skills/consultant/` and `skills/second-opinion/` carry the advisory and explicit consultant routing surfaces
- `skills/external-brigade/` carries the bounded parallel external-helper orchestration surface

This subtree is the Codex runtime source owned by the monorepo. Shared governance and shared references stay one level up; only the provider-specific runtime source lives here.
