# Claude Pack Source

This directory contains the Claude-provider source tree inside the Orchestrarium monorepo.

Use it together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs surface
- [../shared/references/README.md](../shared/references/README.md) for the shared design core
- [../references-claude/README.md](../references-claude/README.md) for the Claude-side provider addendum

Source surface:

- `CLAUDE.md` is the Claude-provider runtime entrypoint in the monorepo source tree
- `agents/` carries role definitions, contracts, team templates, and supporting scripts, including the Claude API wrapper under `agents/scripts/`
- `commands/` carries Claude-side command helpers maintained in this branch, including the bounded parallel external-helper surface `/agents-external-brigade`
- `memory/` carries the optional experience-based feedback surface

This subtree is the Claude runtime source owned by the monorepo. Shared governance and shared references stay one level up; only the provider-specific runtime source lives here.
