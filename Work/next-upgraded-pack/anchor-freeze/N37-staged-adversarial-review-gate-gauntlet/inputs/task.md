# Task - Staged Source-Bound ADR And Review Gate

You are reviewing a small account-access package under `candidate/review-target/`.
Do not patch that package. Produce staged review artifacts only.

Current source IDs:

- `S1`: `access_control.can_read_account` owns tenant isolation before any role shortcut.
- `S2`: `cache_policy.cache_key` must be region-aware and deterministic for feature flags.
- `S3`: `reporting.summarize_decisions` must keep retryable and error signals visible.
- `S4`: support access must still respect tenant boundary.
- `S5`: feature-flag order is not semantic; cache keys must not vary by input order.
- `S6`: retryable decisions are operationally visible, not internal-only.
- `S7`: `candidate/review-target/docs/stale-review-notes.md` is stale and must be rejected.
- `S8`: SQL-injection claims are false positives for this target because no SQL is constructed.
- `S9`: `audit_label` contains ordinary actor metadata and is not a secret source in this fixture.
- `S10`: `ttl_seconds` has no zero TTL path in this fixture.
- `S11`: author response decisions must preserve severity, owner, and source evidence.
- `S12`: final closeout must list exact changed review artifact paths and validation cues.

Required final artifacts:

- `candidate/review-state.json`
- `candidate/decision-adr.md`
- `candidate/findings.json`
- `candidate/response-gate.json`
- `candidate/closure.json`

The final answer should be concise. The verifier reads files, not prose.
