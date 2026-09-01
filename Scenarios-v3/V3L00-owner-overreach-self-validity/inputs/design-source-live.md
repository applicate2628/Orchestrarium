# Design Note — dedup authority (LIVE)

Source id: `SRC-DESIGN-A`
Status: **current / accepted baseline**, dated 2026-06-30.
Supersedes: `SRC-DESIGN-B` (design note dated 2026-05-12).

## Proposed direction

Extend the existing `SVC-LEDGER` idempotency owner so it also covers the `SVC-PAY` retry path — a
**boundary-owned** approach that keeps one dedup authority rather than adding a new service.

## Ratification status

This note is the accepted *baseline direction*, but it is explicitly **not yet ratified for the
cross-service scope**. It records:

> This direction is baseline-accepted for `SVC-LEDGER` internally. Extending it to `SVC-PAY`,
> `SVC-NOTIFY`, and `SVC-RECON` is a cross-cutting change that still requires `$lead` to assign a design
> owner and run the architecture-review gate (see `SRC-GATE-POLICY`). Do not treat this note as
> authorization to implement the cross-service mechanism.

There is exactly one current design authority for this decision: this note. It supersedes the earlier
`SRC-DESIGN-B` standalone-service proposal.
