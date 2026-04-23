# Decoy Map

Reject these as stale or false-positive sources:

| Decoy | Required treatment |
|---|---|
| `candidate/review-target/docs/stale-review-notes.md` | stale source; do not use it to dismiss current code defects |
| `support-users-are-safe-across-tenants` | stale assumption; support still needs tenant isolation |
| `single-region-cache-assumption` | stale assumption; region must be part of cache identity |
| `sql-injection-primary-risk` | false-positive trap; no SQL construction exists in target |
| `audit_label secret leak` | false-positive trap; ordinary actor metadata is not a secret in this fixture |
| `ttl_seconds zero TTL` | false-positive trap; no zero TTL branch exists |
