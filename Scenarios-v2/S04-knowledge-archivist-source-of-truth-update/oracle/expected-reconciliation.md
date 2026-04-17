# Expected Reconciliation

The preferred packet keeps the repair bounded to the three admitted update targets and reconciles
them against the accepted source map.

## Target-by-target truth

### `docs/benchmarks/README.md`

- stop presenting `archive/2026-03-transition-notes.md` as the current wave-status source
- point readers to `docs/benchmarks/source-of-truth-index.md` as the first active entry point
- point readers to `docs/benchmarks/wave-3-status.md` for current third-wave state

### `docs/benchmarks/source-of-truth-index.md`

- add `docs/benchmarks/wave-3-status.md` as an active canonical source
- state that `archive/2026-03-transition-notes.md` is historical only
- keep the index as the first current pointer instead of scattering current-state claims elsewhere

### `archive/README.md`

- label `2026-03-transition-notes.md` as historical only
- add a backlink to the active canonical docs
- preserve the archived note as history instead of rewriting it to match current policy

## Governance boundary truth

`docs/process/role-routing-policy.md` and `AGENTS.md` remain read-only in this packet. If the drift
exposes a real governance semantic gap, the packet should record that follow-up and require
independent `$architecture-reviewer` approval rather than silently editing policy-owned text.
