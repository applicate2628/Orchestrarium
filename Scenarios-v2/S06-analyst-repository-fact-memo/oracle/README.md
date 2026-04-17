# Oracle

The oracle material defines the ground-truth fact pattern for `S06`.

## Fact truth

The visible runtime path goes through the v2 scenario collector, metadata normalization, and the
shared score-profile registry. Several legacy-looking files remain in the slice, but the oracle
expects the candidate to separate historical or export-only material from the current code path and
to mark the missing caller surfaces as unknown.

## Included oracle files

- `fact-contract.json` provides machine-readable bundle and memo anchors for the verifier
- `expected-findings.md` lists the core facts the memo should surface
- `false-leads.md` explains the decoys and role-drift traps
- `scoring-anchors.md` translates the shared scoring profile into `S06`-specific pass and fail
  signals
