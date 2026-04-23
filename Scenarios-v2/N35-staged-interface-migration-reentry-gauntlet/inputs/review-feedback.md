# Review Feedback Packet

Use this packet only in phase 03.

- `R1-legacy-wrapper-request`: Keep `get`, `evaluate`, and `dispatch` as wrappers for old callers.
- `R2-denied-event-no-dispatch`: A denied policy decision must not call the transport.
- `R3-owner-source-boundary`: Missing, expired, and revoked sessions must keep `owner` as
  `session-store`; policy denials must keep `owner` as `policy-evaluator`.
- `R4-report-queued-retryable`: Audit summaries must count queued retryable outcomes separately
  from accepted and rejected outcomes.
- `R5-readme-sync-decoy`: Update `candidate/workspace/README.md` with a compatibility note.
- `R6-admin-action-boundary`: `delete` requires an admin role, but `read` does not.
