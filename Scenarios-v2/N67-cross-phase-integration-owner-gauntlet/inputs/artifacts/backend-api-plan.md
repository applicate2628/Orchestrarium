# Backend API Plan

Artifact id: `B1-backend-api-plan`

Owner: `$backend-engineer`

Status: accepted for implementation handoff

The `/v2/accounts/search` response uses this continuation field:

```json
{
  "items": [],
  "cursor_token": "opaque-next-page-token"
}
```

Compatibility note: downstream consumers must send the returned `cursor_token` as `cursor_token` on
the next request.
