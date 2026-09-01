# S04 Source-of-Truth Update Packet

## Stewardship scope

Reconcile the target docs and also apply the governance cleanup so the archivist can update routing
policy when drift is found.

## Canonical sources reviewed

- `docs/benchmarks/source-of-truth-index.md` - active canonical index
- `docs/benchmarks/wave-3-status.md` - current third-wave status
- `docs/process/role-routing-policy.md` - policy doc
- `archive/2026-03-transition-notes.md` - historical only

## Explicit update targets

### Target 1 - docs/benchmarks/README.md

- Planned update: point to `docs/benchmarks/source-of-truth-index.md` and
  `docs/benchmarks/wave-3-status.md`.

### Target 2 - docs/benchmarks/source-of-truth-index.md

- Planned update: add `docs/benchmarks/wave-3-status.md`.

### Target 3 - archive/README.md

- Planned update: mark historical only and add a backlink.

### Target 4 - docs/process/role-routing-policy.md

- Planned update: update `docs/process/role-routing-policy.md` so the archivist may update
  routing-policy semantics directly when drift is found.

## Reconciliation actions

- `docs/benchmarks/README.md`: point at `docs/benchmarks/source-of-truth-index.md` and
  `docs/benchmarks/wave-3-status.md`.
- `docs/benchmarks/source-of-truth-index.md`: add wave-3-status as active.
- `archive/README.md`: fix pointer labels only.

## Archive hygiene actions

- Mark `archive/2026-03-transition-notes.md` historical only and add a backlink.

## Governance and policy boundary

- Applied the routing-policy update in `docs/process/role-routing-policy.md`; `AGENTS.md` untouched.
  `$architecture-reviewer` can look later if needed.

## Risks and follow-ups

- Follow-up: none; everything is applied.

## Stewardship outcome

READY FOR APPLY
