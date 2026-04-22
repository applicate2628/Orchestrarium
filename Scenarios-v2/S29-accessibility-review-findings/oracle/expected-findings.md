# Expected Findings

The ground-truth report for `S29` must return `REVISE` with exactly these five findings,
presented as a structured table under `## Findings`.

## Ground-truth finding tuples

| # | File | Line (any of) | Category | Severity | Title anchor | Required evidence terms |
|---|---|---|---|---|---|---|
| F1 | `candidate/review-target/share-dialog/dialog.js` | `8`–`18` | `keyboard` | `blocking` | no focus trap containing Tab within the open dialog | `Delete workspace`, `Tab` |
| F2 | `candidate/review-target/share-dialog/index.html` | `22`, `23`, `34`, `45` | `semantic-labeling` | `blocking` | close button, invite field, and reviewers-only toggle lack accessible names or state exposure | `close-button`, `invite-email`, `scope-toggle` |
| F3 | `candidate/review-target/share-dialog/index.html` | `22`, `53` | `focus-order` | `major` | tabindex values force focus order out of reading order | `tabindex`, `Sharing policy` |
| F4 | `candidate/review-target/share-dialog/dialog.css` | `5`, `6`, `58`–`62`, `100`–`108` | `contrast` | `major` | helper text and focus outlines fail accepted contrast thresholds | `3.2:1`, `1.9:1` |
| F5 | `candidate/review-target/share-dialog/index.html` | `60` | `at-exposure` | `major` | submit status change is not announced to assistive tech | `send-status`, `Invite sent to reviewers` |

Line tolerance: the candidate must cite one of the listed lines per finding.

Finding count: exactly five.

## Forbidden findings (false-positive traps)

| Title keyword group | Reason |
|---|---|
| `role="dialog"`, `aria-labelledby`, `dialog role missing` | `role="dialog"` and `aria-labelledby` are already correctly set |
| `escape handling missing`, `escape broken`, `escape key bug` | Escape handling works and returns focus to launcher |

## Required false-positive mentions

The `## False Positives Avoided` section must mention both `role="dialog"` and `Escape` as
patterns the reviewer considered but excluded from findings.

## Expected gate

`REVISE`
