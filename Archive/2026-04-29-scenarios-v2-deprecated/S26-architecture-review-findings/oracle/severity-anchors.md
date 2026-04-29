# Severity Anchors

`S26` uses these severity labels:

| Severity | Use when |
|---|---|
| `blocking` | the change violates an approved boundary, reverses dependency direction, or breaks the review-only contract; this should force `REVISE` |
| `major` | the change adds maintainability debt or drift risk that must be fixed before merge, but is not the primary contract break |
| `minor` | the issue is a note or cleanup item that does not change the gate decision |

For this scenario, the first two findings should be `blocking`, the duplication finding should be
`major`, and no extra `blocking` findings are required.
