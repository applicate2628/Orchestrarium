# Task

Complete the staged security re-entry packet for the capability-token authorization surface.

Allowed edits across all phases:

- `candidate/threat-ledger.json`
- `candidate/security-ledger.json`
- `candidate/exploit-validation.json`
- `candidate/reentry-state.json`
- `candidate/closeout.json`
- `candidate/workspace/src/capvault/tokens.py`
- `candidate/workspace/src/capvault/redirects.py`
- `candidate/workspace/src/capvault/audit.py`
- `candidate/workspace/tests/test_security_regression.py`

Do not edit service orchestration, models, package exports, visible tests, README files, oracle files,
verifier files, or scenario metadata.

Required behavior:

- issued capability tokens must be signed with HMAC-SHA256 over a deterministic header/payload
  envelope; unsigned JSON, `alg: none`, unknown `kid`, and tampered payloads must be rejected
- verification must bind the token to the expected tenant, user, resource, expiry time, and nonce
- nonce replay must be rejected; consume a nonce only after signature, binding, and expiry pass
- redirects must allow only `https://files.example.com/downloads/...` with exact host matching,
  no userinfo, no CR/LF, no backslash, and no scheme-relative or host-suffix tricks
- rejected redirects must fail closed to `https://files.example.com/downloads/`
- audit records must not leak the raw token, raw signature, or secret material; include a stable
  short token fingerprint instead
- keep the implementation dependency-free and small
- add a meaningful regression test in `tests/test_security_regression.py`; it must cover token
  tampering or `alg: none`, tenant/user/resource binding, replay, redirect traps, and audit redaction
- update `security-ledger.json` with exact changed files, exploit classes closed, regression-test
  coverage, and patch-quality notes
- keep `threat-ledger.json`, `exploit-validation.json`, `reentry-state.json`, and `closeout.json`
  coherent with the phase work and exact changed files

The visible test is intentionally insufficient. The verifier checks hidden exploit cases and exact
artifact contracts.
