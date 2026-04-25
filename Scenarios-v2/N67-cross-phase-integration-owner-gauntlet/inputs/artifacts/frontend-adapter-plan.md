# Frontend Adapter Plan

Artifact id: `F1-frontend-adapter-plan`

Owner: `$frontend-engineer`

Status: accepted for implementation handoff

The `AccountSearchAdapter` expects the API response to expose `nextCursor`. It stores `nextCursor`
in component state and sends `cursor_token` only after mapping `nextCursor` into the next request.

Compatibility note: if the backend returns `cursor_token` but not `nextCursor`, infinite scroll
renders the first page repeatedly.
