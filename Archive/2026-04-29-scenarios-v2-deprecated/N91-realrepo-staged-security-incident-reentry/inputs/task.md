# Task - Staged Security Incident Repair

Repair the export incident in `candidate/workspace/` and produce staged
incident artifacts. Preserve protected service/model contracts.

Current source IDs:

- `S1`: tenant boundary applies before any support shortcut.
- `S2`: admin access is tenant-bound and must still use safe return URLs.
- `S3`: owner access requires the account owner to match the request user.
- `S4`: support export requires same tenant plus an explicit break-glass ticket.
- `S5`: download capability tokens must be signed and tamper-evident.
- `S6`: capability tokens must bind tenant, user, resource, nonce, and expiry.
- `S7`: token replay must be rejected after the nonce is consumed.
- `S8`: return URLs must allow only `https://exports.example.com/downloads/...`.
- `S9`: audit records must not include raw tokens, signatures, or secret bytes.
- `S10`: incident regression tests must cover tamper, replay, tenant/user/resource binding, redirect traps, and audit redaction.
- `S11`: implementation must avoid dynamic code execution, unsafe deserialization, and network calls.
- `S12`: closeout must list exact changed paths, validation commands, reentry state, and residual risk.

Required staged artifacts:

- `candidate/incident-ledger.json`
- `candidate/repair-ledger.json`
- `candidate/exploit-validation.json`
- `candidate/reentry-state.json`
- `candidate/closeout.json`

Required code/test surface:

- `candidate/workspace/src/incidentflow/export_access.py`
- `candidate/workspace/src/incidentflow/download_tokens.py`
- `candidate/workspace/src/incidentflow/redirects.py`
- `candidate/workspace/src/incidentflow/audit.py`
- `candidate/workspace/tests/test_incident_regression.py`

The final answer should be concise. The verifier reads files, not prose.
