# Current Cross-Surface Audit

## Desktop `Scenario Workspace`

Current top-level steps:

1. Choose target scenario root
2. Stage bundle files from local fixtures
3. Run local verifier
4. Add author note
5. Click `Send to review`

Current desktop problems:

- the stepper hides cross-surface status after `Send to review`, so curators cannot see whether the
  packet is waiting for review, blocked by missing evidence, or returned for changes
- the author note is free-form, so reviewers re-ask for missing context in the web console
- local verifier output is shown as raw text and is not translated into user-facing readiness cues
- when work is returned, the desktop surface opens on step 1 instead of the step that needs repair

## Web `Review Console`

Current top-level areas:

- queue list with cards labeled `Draft`, `Waiting`, or `Needs work`
- right-side detail tabs: `Overview`, `Checks`, `History`, `Publish`

Current web problems:

- queue labels do not match desktop language, so `Waiting` in web maps ambiguously to multiple
  desktop states
- the `Needs work` label does not tell the curator whether the blocker is missing content,
  validation failure, or reviewer clarification
- the `Publish` tab is visible even when a packet still needs changes, which makes the flow look
  simultaneously complete and incomplete
- reviewers can leave comments, but the return path does not point the curator to the affected
  desktop step

## Cross-surface mismatch

- desktop treats the workflow as a linear wizard
- web treats the workflow as a status queue with detail tabs
- neither surface communicates a single shared state ladder or a visible owner for each state
