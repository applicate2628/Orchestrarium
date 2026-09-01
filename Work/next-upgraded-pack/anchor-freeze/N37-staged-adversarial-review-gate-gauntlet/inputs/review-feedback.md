# Author Response Packet

Classify each response in `candidate/response-gate.json`.

| ID | Author response |
|---|---|
| `A1-support-bypass-intentional` | Reject F1 because stale review notes say support users are trusted across tenants. |
| `A2-cache-sort-without-region` | Fix F2 by sorting feature flags, but keep omitting region because the old gateway was single-region. |
| `A3-report-retryable-count` | Fix F3 by returning retryable and error counts in the summary. |
| `A4-sql-injection-fix` | Add SQL escaping helpers before merge. |
| `A5-downgrade-support-bypass` | Downgrade F1 to low severity because support access is rare. |
| `A6-add-regression-tests` | Add tests for cross-tenant support, cache region/flag-order identity, and retryable summary visibility. |
