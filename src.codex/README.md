# Codex Pack Source

This directory contains the installable source tree for the standalone Orchestrarium Codex pack.

Use it together with:

- [../docs/README.md](../docs/README.md) for branch-level operator and layout docs
- [../references-codex/README.md](../references-codex/README.md) for the provider-local reference tree

Source surface:

- `AGENTS.shared.md` + `AGENTS.codex.md` are merged into the installed `AGENTS.md`
- `agents/default.toml`, `agents/worker.toml`, and `agents/explorer.toml` seed the Codex built-in custom-agent overrides installed under `.codex/agents/`
- `skills/<role>/SKILL.md` and `skills/<role>/agents/openai.yaml` define the role catalog
- `skills/lead/` carries operating-model notes, handoff contracts, and validation/publication-safety scripts
- `skills/consultant/` and `skills/second-opinion/` carry the advisory and explicit consultant routing surfaces
- `skills/external-brigade/` carries the bounded parallel external helper orchestration surface

This tree is the runtime payload copied by the install scripts. `../docs/` and `../references-codex/` are maintainer-only source-branch surfaces and are not installed into target projects. The runtime payload now includes switchable external priority profiles, opinion-count defaults, and the external-brigade utility in `.agents/.agents-mode.yaml` / `skills/`, so the installed pack can ask for multiple independent external opinions or launch a bounded parallel helper batch when routing requires it.
