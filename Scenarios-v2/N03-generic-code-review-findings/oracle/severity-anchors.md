# Severity Anchors

`N03` uses these severity labels:

| Severity | Use when |
|---|---|
| `blocking` | the change breaks the reviewer's core evidence surface or hides a required touched file set; this should force `REVISE` |
| `major` | the change loses review evidence or diagnosability in a way that must be fixed before merge |
| `minor` | the issue is real but does not change the gate decision |

For this scenario, the changed-path finding should be `blocking`, the dedupe and hunk-parsing
findings should be `major`, and no extra `blocking` findings are required.
