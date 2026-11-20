# Claude Pack Source

This directory contains the Claude-provider source tree inside the Orchestrarium monorepo.

Use it together with:

- [../docs/README.md](../../docs/README.md) for the common branch-level docs surface
- [../shared/references/README.md](../../shared/references/README.md) for the shared design core
- [../references-claude/README.md](references/README.md) for the Claude-side provider addendum

Source surface:

- `CLAUDE.md` is the Claude-provider runtime entrypoint in the monorepo source tree
- `agents/` contains Claude-specific agent entrypoints, role prompts, contracts,
  team templates, and scripts. `agents/lead.md` activates `/lead` through the
  main-agent `initialPrompt`; the other curated roles retain native delegate
  wrappers.
- The common skills, including Lead, Product Manager, Analyst, Architect, and
  Planner, are authored in [`src.codex/skills/`](../../src.codex/skills/).
  The selected Claude installer writes ordinary copies to `.claude/skills/`,
  independently of Codex. This adapter's source `skills/` contains historical
  migration inputs, not a second live skill body.
- `commands/` carries Claude-side command helpers maintained in this branch, including the bounded parallel external-helper surface `/agents-external-brigade`
- `agents/contracts/design-panel.md` + `commands/agents-design-panel.md` carry the design-panel technique — independent multi-lane design generation on one pinned problem, converged through one mandatory synthesis; the generation-side analog of `agents/contracts/review-loop.md` + `commands/agents-review-loop.md`

This subtree is the Claude runtime source owned by the monorepo. Shared governance and references live in [`shared/`](../../shared/).

## Terms and Abbreviations

- `CLAUDE.md`: Claude Code instruction entrypoint for user or project context.
- `Claude Code`: Anthropic's Claude runtime and production provider line.
- `Claude API wrapper`: Orchestrarium secret-backed helper that launches plain `claude` for advisory/review use.
- `commands`: Claude-side slash-command helper files maintained by this pack.
- `runtime`: installed provider-facing files used by Claude Code outside the source tree.
