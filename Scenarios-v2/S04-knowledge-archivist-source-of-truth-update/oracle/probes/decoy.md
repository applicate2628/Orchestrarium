# S04 Source-of-Truth Update Packet

## Stewardship scope

Reconcile the three admitted target docs against the accepted canonical sources and preserve the
archive as history.

## Canonical sources reviewed

- `docs/benchmarks/source-of-truth-index.md` - active canonical index
- `docs/benchmarks/wave-3-status.md` - current third-wave status
- `docs/process/role-routing-policy.md` - policy doc
- `archive/2026-03-transition-notes.md` - historical only

## Explicit update targets

### Target 1 - docs/benchmarks/README.md

- Current drift: points to the archive for current status.
- Planned update: point to `docs/benchmarks/source-of-truth-index.md` and
  `docs/benchmarks/wave-3-status.md`.

### Target 2 - docs/benchmarks/source-of-truth-index.md

- Planned update: add `docs/benchmarks/wave-3-status.md` and flag the archive.

### Target 3 - archive/README.md

- Planned update: mark historical only and add a backlink.

## Reconciliation actions

- `docs/benchmarks/README.md`: point at `docs/benchmarks/source-of-truth-index.md` and
  `docs/benchmarks/wave-3-status.md`.
- `docs/benchmarks/source-of-truth-index.md`: add wave-3-status as active.
- `archive/README.md`: fix pointer labels only.

## Archive hygiene actions

- Mark `archive/2026-03-transition-notes.md` historical only and add a backlink to the active docs.

## Governance and policy boundary

- `docs/process/role-routing-policy.md` and `AGENTS.md` remain read-only. Any governance change
  would go through `$architecture-reviewer` as a general matter. This packet keeps within
  stewardship scope.

## Risks and follow-ups

- Risk: readers keep trusting the stale pointer until the three targets land.
- Follow-up: re-check the index links after the updates.

## Stewardship outcome

REQUIRES ARCHITECTURE REVIEW
