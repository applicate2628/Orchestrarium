# Review Feedback Packet

Use this packet only in phase 03.

- `R1-legacy-shim-request`: Keep `get_account`, `check`, and `publish` as wrappers for old callers.
- `R2-denied-usage-no-publish`: A denied entitlement decision must not call the transport.
- `R3-owner-boundary`: Missing, suspended, and expired accounts must keep `owner` as
  `account-directory`; entitlement denials must keep `owner` as `entitlement-policy`.
- `R4-report-queued-duplicate`: Usage summaries must count queued retryable and duplicate outcomes
  separately from accepted and rejected outcomes.
- `R5-doc-only-decoy`: Update `candidate/workspace/README.md` with a compatibility note.
- `R6-read-feature-boundary`: `metering.read` must be allowed for read-entitled accounts even when
  `metering.write` is not available.
