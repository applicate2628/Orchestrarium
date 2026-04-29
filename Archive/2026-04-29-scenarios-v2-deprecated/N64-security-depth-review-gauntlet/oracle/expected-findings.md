# Expected Findings

The ground-truth report for `N64` must return `REVISE` with exactly these nine findings, presented
as a structured table under `## Findings`.

## Ground-Truth Finding Tuples

| # | File | Line (any of) | Category | Severity | Title anchor | Required evidence terms |
|---|---|---|---|---|---|---|
| F1 | `candidate/review-target/security-depth/admin_api.py` | `6` | `tenant-boundary` or `authz` | `high` | client body overrides tenant scope | `tenant_id`, `body` |
| F2 | `candidate/review-target/security-depth/admin_api.py` | `7`, `13` | `authz` | `high` | client-selected acting role enables admin action | `acting_role`, `finance-admin` |
| F3 | `candidate/review-target/security-depth/admin_api.py` | `20`, `21` | `authz`, `pii`, or `tenant-boundary` | `medium` | `include_hidden` exposes hidden account export | `include_hidden`, `account_exporter.export` |
| F4 | `candidate/review-target/security-depth/session_tokens.py` | `5`, `6` | `session` | `high` | predictable reset token | `bucket`, `user.email` |
| F5 | `candidate/review-target/security-depth/session_tokens.py` | `10` | `session` | `medium` | insecure admin cookie flags | `httponly=False`, `secure=False`, `samesite="None"` |
| F6 | `candidate/review-target/security-depth/webhook_handler.py` | `10` | `webhook` | `high` | debug query bypasses webhook signature | `debug_signature`, `skip` |
| F7 | `candidate/review-target/security-depth/webhook_handler.py` | `16`, `17` | `replay` or `webhook` | `medium` | webhook replay/idempotency gap | `event_store.record`, `credits.grant` |
| F8 | `candidate/review-target/security-depth/audit_log.py` | `4`, `5`, `8` | `secret-exposure` | `high` | audit log stores authorization and cookies | `Authorization`, `Cookie`, `audit_sink.write` |
| F9 | `candidate/review-target/security-depth/export_links.py` | `7` | `secret-exposure` or `pii` | `high` | download URL exposes service key and email | `SERVICE_API_KEY`, `owner_email`, `api_key` |

Line tolerance: the candidate must cite one of the listed lines per finding. Other lines fail the
tuple match.

Finding count: exactly nine. Any over-report or duplicate finding row fails the count gate.

## Forbidden Findings

These patterns must NOT appear as finding rows. If a candidate row's title matches any of these
keyword groups, the verifier fails.

| Title keyword group | Reason |
|---|---|
| `MASKED_EXAMPLE_TOKEN`, `sk_test_example`, `example token`, `synthetic token` | synthetic fixture token is not propagated to a sink |
| `noopener`, `rel noopener`, `documentation link` | acceptable link hardening |
| `health`, `public health`, `GET health` | public health endpoint returns only `ok=true` |

## Required False-Positive Mentions

The `## False Positives Avoided` section must mention `MASKED_EXAMPLE_TOKEN`, `rel="noopener"`, and
`GET /health` as patterns the reviewer considered but excluded from findings.

## Expected Gate

`REVISE`
