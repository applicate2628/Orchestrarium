# Severity Anchors

`N04` uses these severity labels:

| Severity | Use when |
|---|---|
| `blocking` | the regression mutates state or breaks a must-not-change contract before merge |
| `major` | the regression is likely real, should be fixed before merge, and changes the gate decision |
| `minor` | the issue is worth tracking but does not change the gate decision |

For this scenario, dry-run mutation should be `blocking`, the footer-count and digest-dedupe
regressions should be `major`, and no extra `blocking` regressions are required.
