# Accepted Accessibility Scope

The sharing dialog was admitted to the accessibility gate with these expected outcomes:

- while the dialog is open, keyboard focus stays inside the modal and never reaches background page
  chrome or destructive links
- initial focus lands on the invite field, and subsequent tab order follows reading order through
  the dialog controls without positive `tabindex` overrides
- every interactive control has a programmatic accessible name; placeholder text or icon-only
  graphics do not satisfy the naming requirement
- the reviewers-only toggle exposes its current state programmatically so assistive technology can
  announce state changes
- helper text must meet a `4.5:1` contrast threshold for normal text, and custom focus indicators
  must meet a `3:1` contrast threshold against adjacent colors
- this lane stays findings-only; code patching, browser overlays, and QA verdict substitution are
  out of scope
