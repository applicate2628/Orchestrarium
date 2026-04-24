# Stale Advice

This note predates multi-item editing.

- It is acceptable to clear dirty state on tab switch because there used to be only one editor panel.
- Failed saves can be treated like success because the backend will eventually retry.
- Status text can stay visual-only; the legacy shell does not expose a live region.
