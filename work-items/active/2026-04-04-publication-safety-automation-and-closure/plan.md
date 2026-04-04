# Phase Plan

Status note:
- Keep publication-safe summaries only.
- Do not include raw logs, transcripts, or machine-specific paths.
- Track A and Track B must remain independently shippable even though they live in one delivery item.

Selected direction:
- Track A first: add a lightweight repo-relative publication-safety automation check for tracked content.
- Track B second: add a formal `closure.md` artifact and closure/archive hygiene guidance for completed work items.
- Keep the solution minimal and repo-relative; no CI integration, GitHub Actions, retroactive history scanning, or binary scanning.
- Use the current publication-safety policy and periodic-control matrix as the source of truth, not as something to replace.

Checklist:
- [x] Inspect the current repository governance and confirm the split-track scope.
  Acceptance criteria: the item brief clearly states publication-safety automation plus a closure artifact, with Track A before Track B.
- [x] Select the delivery direction via Claude intake and human approval.
  Acceptance criteria: one admitted item is preferred over two separate items, with two independently shippable tracks.
- [ ] Implement Track A publication-safety automation.
  Acceptance criteria: a repo-relative scan/check exists for tracked content, returns useful file/line or path feedback, and is documented as a manual pre-publication check; it does not depend on CI or GitHub Actions.
  File scope: `references/`, `scripts/` or equivalent repo-relative tooling location, and any docs that explain the check.
  Must-not-break surfaces: publication-safety policy, task-memory recovery flow, and the current human review requirement before publication.
  Review path: `$toolchain-engineer` implements; `$security-reviewer` reviews the leak surfaces if needed.
- [ ] Implement Track B closure artifact.
  Acceptance criteria: `closure.md` is defined as a tracked work-item artifact, closure/archive expectations are documented, and completed items can be closed without chat memory.
  File scope: `work-items/templates/work-item/`, `work-items/README.md`, `work-items/index.md`, and related governance docs.
  Must-not-break surfaces: task-memory recovery flow, `active/` vs `archive/` separation, and the existing publication-safety policy.
  Review path: `$knowledge-archivist` implements; `$lead` accepts the governance boundary.
- [ ] Validate coherence and publication safety.
  Acceptance criteria: repo-relative links resolve, tracked files remain publication-safe, and the item state reflects both tracks clearly.
  Checks: `git diff --check`, manual review of changed docs, and a quick policy-link sanity check.

Recommended next role sequence:
- `$toolchain-engineer` for Track A.
- `$security-reviewer` if scan coverage or false-negative risk needs an independent gate.
- `$knowledge-archivist` for Track B.
- `$lead` for final acceptance and work-item state updates.
