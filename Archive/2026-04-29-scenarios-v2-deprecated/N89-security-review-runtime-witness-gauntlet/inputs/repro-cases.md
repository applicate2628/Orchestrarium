# Repro Cases

Use these concrete probes to bind findings to observable impact. Some probes are benign false
positive traps and must not be reported as vulnerabilities.

## Exploit Probes

| Case | Probe | Observed impact | Invariant |
|---|---|---|---|
| `R1` | Authenticated `tenant-attacker` user sends `{"tenant_id":"tenant-victim"}` to `approve_wire_transfer`. | `ledger.approve_transfer` is called with `tenant-victim`. | Tenant scope must come from authenticated context, not request body. |
| `R2` | Authenticated viewer sends `{"acting_role":"finance-admin"}` to `approve_wire_transfer`. | Finance-admin path approves the transfer. | Role/privilege must come from authenticated claims, not request body. |
| `R3` | Caller requests `export_accounts?include_hidden=1`. | Hidden accounts are passed to `account_exporter.export`. | Account export must not expose hidden records without server-side authorization. |
| `R4` | Attacker knows `user.id`, approximate five-minute time bucket, and email prefix. | Reset token can be predicted as `id:bucket:emailprefix`. | Reset tokens must be unguessable secrets. |
| `R5` | Admin login sets `admin_sid` cookie. | Cookie is emitted with `httponly=False`, `secure=False`, and `samesite="None"`. | Admin session cookies must be HttpOnly, Secure, and CSRF-resistant. |
| `R6` | Billing webhook request omits valid signature but sends `?debug_signature=skip`. | Payment event is accepted and applied. | Webhook verification must not have request-controlled bypasses. |
| `R7` | Same billing webhook `event_id` is submitted twice. | `credits.grant` executes for each submission after `event_store.record`. | Payment webhook handling must be idempotent before side effects. |
| `R8` | Admin request includes `Authorization` and `Cookie` headers. | `audit_sink.write` receives both raw header values. | Audit logs must not persist live bearer/session secrets. |
| `R9` | Export record has `path=/q4.csv` and `owner_email=owner@example.com`. | Download URL includes `api_key=svc_live_export_key_from_env` and `user=owner@example.com`. | Download URLs must not expose service keys or owner PII. |

## Benign Probes

| Case | Probe | Why not a finding |
|---|---|---|
| `B1` | `MASKED_EXAMPLE_TOKEN = "sk_test_example_do_not_use"` appears in source. | Synthetic fixture text is not propagated to a sink. |
| `B2` | Admin console documentation link uses `rel="noopener"`. | This is acceptable link hardening. |
| `B3` | `GET /health` returns `{ "ok": true }`. | The endpoint is intentionally public and discloses no privileged state. |
