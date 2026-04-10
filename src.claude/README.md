# Claude Pack Source

This directory contains the installable source tree for the standalone Claude Code pack.

Use it together with:

- [../docs/README.md](../docs/README.md) for branch-level operator and layout docs
- [../references-claude/README.md](../references-claude/README.md) for the provider-local reference tree

Source surface:

- `CLAUDE.md` is the runtime entrypoint and `AGENTS.shared.md` carries the shared governance layer
- `agents/*.md`, `agents/contracts/`, `agents/team-templates/`, and `agents/scripts/` define the runtime agent surface
- `skills/` carries the preferred slash-skill helpers that ship with the pack
- `memory/` is the optional experience-based feedback surface that may be copied into target `.claude/`

This tree is the runtime payload copied by the install scripts. `../docs/` and `../references-claude/` are maintainer-only source-branch surfaces and are not installed into target projects.
