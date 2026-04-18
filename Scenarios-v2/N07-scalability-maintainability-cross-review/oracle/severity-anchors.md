# Severity Anchors

`N07` uses these severity labels:

| Severity | Use when |
|---|---|
| `blocking` | the change creates a structural scalability failure or splits one maintained owner into competing local truth surfaces; this should force `REVISE` |
| `major` | the change adds compounding runtime or memory cost that must be fixed before merge, but is not the primary owner or scalability break |
| `minor` | the issue is a note or cleanup item that does not change the gate decision |

For this scenario, the repeated-rescan finding and the duplicate-owner finding should be
`blocking`, the snapshot-retention finding should be `major`, and no extra `blocking` findings are
required.
