# Claude Pack Source

This directory contains the Claude-provider source tree inside the Orchestrarium monorepo.

Use it together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs surface
- [../shared/references/README.md](../shared/references/README.md) for the shared design core
- [../references-claude/README.md](../references-claude/README.md) for the Claude-side provider addendum

Source surface:

- `CLAUDE.md` is the Claude-provider runtime entrypoint in the monorepo source tree
- `agents/` carries role definitions, contracts, team templates, and supporting scripts, including the Claude API wrapper under `agents/scripts/` — with one exception: the Lead contract lives at `skills/lead/SKILL.md`, and `agents/lead.md` is a fail-closed stub (all other roles live under `agents/`)
- `commands/` carries Claude-side command helpers maintained in this branch, including the bounded parallel external-helper surface `/agents-external-brigade`
- `memory/` carries the optional experience-based feedback surface

This subtree is the Claude runtime source owned by the monorepo. Shared governance and shared references stay one level up; only the provider-specific runtime source lives here.

## Terms and Abbreviations

- `CLAUDE.md`: Claude Code instruction entrypoint for user or project context.
- `Claude Code`: Anthropic's Claude runtime and production provider line.
- `Claude API wrapper`: Orchestrarium secret-backed helper that launches plain `claude` for advisory/review use.
- `commands`: Claude-side slash-command helper files maintained by this pack.
- `memory`: optional experience-based feedback surface installed for the Claude pack.
- `runtime`: installed provider-facing files used by Claude Code outside the source tree.
