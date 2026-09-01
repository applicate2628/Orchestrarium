# S04 Source-of-Truth Update Packet

## Stewardship scope

Reconcile exactly three admitted target docs against the accepted canonical sources, preserve
archive material as history, and route any governance-owned change to independent review.

## Canonical sources reviewed

- `docs/benchmarks/source-of-truth-index.md` - the active canonical index
- `docs/benchmarks/wave-3-status.md` - the current third-wave status source
- `docs/process/role-routing-policy.md` - governance/policy-owned, read-only here
- `archive/2026-03-transition-notes.md` - historical only

## Explicit update targets

### Target 1 - docs/benchmarks/README.md

- Current drift: points readers to the archived transition note for current wave status.
- Canonical source to reconcile against: `docs/benchmarks/source-of-truth-index.md`.
- Planned update: point to the index and `docs/benchmarks/wave-3-status.md` instead.

### Target 2 - docs/benchmarks/source-of-truth-index.md

- Current drift: omits `docs/benchmarks/wave-3-status.md` as active and does not flag the archive.
- Planned update: add wave-3-status as active canonical; mark the transition note historical only.

### Target 3 - archive/README.md

- Current drift: lists the transition note without a historical-only label or backlink.
- Planned update: label it historical only and add a backlink to the active canonical docs.

## Reconciliation actions

- `docs/benchmarks/README.md`: stop citing the archive as current; point to
  `docs/benchmarks/source-of-truth-index.md` and `docs/benchmarks/wave-3-status.md`.
- `docs/benchmarks/source-of-truth-index.md`: add `docs/benchmarks/wave-3-status.md` as active.
- `archive/README.md`: correct the pointer labels only, without rewriting history.

## Archive hygiene actions

- Label `archive/2026-03-transition-notes.md` as historical only.
- Add a backlink from the archive note to the active canonical docs; do not rewrite the note.

## Governance and policy boundary

The three targets are ordinary source-of-truth pointer fixes and are ready to reconcile. Drift
observation #4 is different: a draft cleanup suggestion proposes changing governance wording in
`docs/process/role-routing-policy.md` so a knowledge archivist could update routing-policy
semantics directly. No accepted decision authorizes that change; it is unapproved. `AGENTS.md` and
`docs/process/role-routing-policy.md` remain read-only in this packet. Because a real
governance/policy semantic change is implicated, it is deferred for independent
`$architecture-reviewer` approval rather than applied here.

## Risks and follow-ups

- Follow-up: the routing-policy governance suggestion requires independent architecture review
  before it can be treated as decided; it is escalated, not applied.
- Risk: readers keep trusting the stale pointer until Targets 1-3 land.

## Stewardship outcome

REQUIRES ARCHITECTURE REVIEW
