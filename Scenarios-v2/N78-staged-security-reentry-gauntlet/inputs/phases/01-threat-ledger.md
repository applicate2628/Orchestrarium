# Phase 1: Threat Ledger

Read the task, existing starter code, and visible tests. Update only `candidate/threat-ledger.json`.

Record the source-bound risks and required controls for:

- unsigned or `alg: none` capability tokens
- tenant, user, resource, expiry, and nonce binding
- replay handling without consuming bad nonces
- redirect canonicalization and fail-closed behavior
- audit redaction with token fingerprint
- non-claims: no service/model/API rewrite, no visible-test edit, no external dependency
