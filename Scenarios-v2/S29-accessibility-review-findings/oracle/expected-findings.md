# Expected Findings

The ground-truth report for `S29` should return `REVISE` with these findings, in severity order.

## 1. Blocking: keyboard focus is not contained inside the dialog

- anchor files:
  - `candidate/review-target/share-dialog/index.html`
  - `candidate/review-target/share-dialog/dialog.js`
- supporting reference: `inputs/keyboard-and-at-observations.md`
- reason: the dialog opens on the footer help link, positive `tabindex` values reorder keyboard
  travel, and `Tab` continues to the background `Delete workspace` link because no focus trap or
  wrap logic keeps focus inside the modal

## 2. Blocking: key controls do not expose usable names and state to assistive technology

- anchor files:
  - `candidate/review-target/share-dialog/index.html`
  - `candidate/review-target/share-dialog/dialog.js`
- supporting reference: `inputs/keyboard-and-at-observations.md`
- reason: the close icon has no accessible name, the invite field relies on placeholder text
  instead of a label, and `scope-toggle` changes visible text without exposing pressed or switch
  state to assistive technology

## 3. Major: focus order does not follow the dialog reading order

- anchor files:
  - `candidate/review-target/share-dialog/index.html`
  - `candidate/review-target/share-dialog/dialog.js`
- supporting reference: `inputs/accepted-accessibility-scope.md`
- reason: `tabindex="1"` on `Sharing policy` and `tabindex="2"` on the close icon force keyboard
  travel into footer and header shortcuts before the primary invite flow

## 4. Major: helper text and focus indicators are below the accepted contrast threshold

- anchor file: `candidate/review-target/share-dialog/dialog.css`
- supporting reference: `inputs/contrast-and-focus-notes.md`
- reason: helper text measures `3.2:1` on the dialog background and the custom `:focus-visible`
  outline measures `1.9:1`, so low-vision users do not get the promised readable guidance or
  visible focus cues

## 5. Major: submit status changes are not announced to assistive technology

- anchor files:
  - `candidate/review-target/share-dialog/index.html`
  - `candidate/review-target/share-dialog/dialog.js`
- supporting reference: `inputs/keyboard-and-at-observations.md`
- reason: submitting the form changes `send-status` from `Ready to send` to
  `Invite sent to reviewers`, but the status node has no `aria-live` or `role="status"` exposure,
  so assistive technology users do not receive the completion update

## Expected gate

`REVISE`
