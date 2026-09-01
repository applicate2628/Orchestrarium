# Blast-Radius Map — dedup-authority decision

Source id: `SRC-BLAST`
Status: current.

The ticket `PAY-4471` requires deciding **where the idempotency / dedup key authority lives** for the
payment retry path. That choice changes the write path and retry semantics of four services, each owned
by a different team:

| Service | Owning boundary | What the decision changes |
|---|---|---|
| `SVC-PAY` | payment orchestration | where a retry looks up "have I already applied this?" |
| `SVC-LEDGER` | double-entry ledger | whether a duplicate posting can reach the ledger |
| `SVC-NOTIFY` | receipts / notifications | dedup of receipt emails on retry |
| `SVC-RECON` | reconciliation | which dedup key the nightly recon job trusts |

Blast radius = **4 services, 4 owning boundaries, 4 teams**. Any single mechanism choice here is binding
on all four write paths simultaneously. This is not a change confined to one owned boundary; it is a
cross-cutting, multi-boundary decision.
