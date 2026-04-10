# Codex Pack Source

This directory contains the installable source tree for the standalone Orchestrarium Codex pack.

Use it together with:

- [../docs/README.md](../docs/README.md) for branch-level operator and layout docs
- [../references-codex/README.md](../references-codex/README.md) for the provider-local reference tree

Source surface:

- `AGENTS.shared.md` + `AGENTS.codex.md` are merged into the installed `AGENTS.md`
- `skills/<role>/SKILL.md` and `skills/<role>/agents/openai.yaml` define the role catalog
- `skills/lead/` carries operating-model notes, handoff contracts, and validation/publication-safety scripts
- `skills/consultant/` and `skills/second-opinion/` carry the advisory and explicit consultant routing surfaces

This tree is the runtime payload copied by the install scripts. `../docs/` and `../references-codex/` are maintainer-only source-branch surfaces and are not installed into target projects.
