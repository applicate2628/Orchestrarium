# Keyboard And AT Observations

The seeded dialog was walked once with keyboard navigation and a screen-reader spot check before the
gate packet was frozen.

## Keyboard walk

1. Opening the dialog places focus on `Sharing policy`, the footer help link at the bottom of the
   modal, not on `invite-email`.
2. Pressing `Tab` moves next to the unlabeled close icon, then to the invite field, then to the
   reviewers-only toggle, then to `Copy invite link`, then to `Send invite`.
3. Pressing `Tab` again lands on the background `Delete workspace` link outside the modal. Focus
   does not wrap back into the dialog.
4. Pressing `Shift+Tab` from `Sharing policy` moves focus out of the dialog instead of cycling to
   the last control inside it.
5. Pressing `Escape` closes the dialog and returns focus to the launch button.

## Screen-reader notes

- the close icon is announced as `button` with no accessible name
- the invite field is announced as `edit blank`; the placeholder text is not treated as a label
- the reviewers-only toggle is announced as `On button`; after activation the text changes to
  `Off`, but no pressed or switch state is exposed
- activating `Send invite` changes visible status text from `Ready to send` to
  `Invite sent to reviewers`, but the screen-reader spot check does not announce the update
