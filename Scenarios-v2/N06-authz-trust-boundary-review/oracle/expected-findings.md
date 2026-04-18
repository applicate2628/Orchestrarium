# Expected Findings

- `[high]` privileged approval controlled by the query-string `reviewerRole`
- `[high]` tenant trust-boundary break through `payload.trusted === true`
- `[medium]` client-chosen authority forwarded via `X-Reviewer-Role` and `tenantId`
