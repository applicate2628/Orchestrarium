# Claude Pack Source

This directory contains the Claude-provider source tree inside the Orchestrarium monorepo.

Use it together with:

- [../docs/README.md](../docs/README.md) for the common branch-level docs surface
- [../shared/references/README.md](../shared/references/README.md) for the shared design core
- [../references-claude/README.md](../references-claude/README.md) for the Claude-side provider addendum

Source surface:

- `CLAUDE.md` is the Claude-provider runtime entrypoint in the monorepo source tree
- `agents/` carries role definitions, contracts, team templates, and supporting scripts, including the Claude API wrapper under `agents/scripts/` — with a curated exception: five roles keep their canonical contracts at `skills/<role>/SKILL.md`. `lead` uses the documented main-agent `initialPrompt: /lead` to load that contract while retaining its fail-closed stale-dispatch branch; the four duals `product-manager`, `analyst`, `architect`, `planner` use thin delegate wrappers loading the same-named skill. Every other role's canonical contract lives under `agents/`.
- `skills/` carries the curated inline role-skills (`lead`, `product-manager`, `analyst`, `architect`, `planner`) and the Claude-side common skills
- `commands/` carries Claude-side command helpers maintained in this branch, including the bounded parallel external-helper surface `/agents-external-brigade`
- `agents/contracts/design-panel.md` + `commands/agents-design-panel.md` carry the design-panel technique — independent multi-lane design generation on one pinned problem, converged through one mandatory synthesis; the generation-side analog of `agents/contracts/review-loop.md` + `commands/agents-review-loop.md`

This subtree is the Claude runtime source owned by the monorepo. Shared governance and shared references stay one level up; only the provider-specific runtime source lives here.

## Terms and Abbreviations

- `CLAUDE.md`: Claude Code instruction entrypoint for user or project context.
- `Claude Code`: Anthropic's Claude runtime and production provider line.
- `Claude API wrapper`: Orchestrarium secret-backed helper that launches plain `claude` for advisory/review use.
- `commands`: Claude-side slash-command helper files maintained by this pack.
- `runtime`: installed provider-facing files used by Claude Code outside the source tree.
