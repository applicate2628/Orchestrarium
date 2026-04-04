# Phase Plan

Status note:
- Claude second opinion is required before the final wording is selected because this is a control-plane governance patch.

Selected direction:
- Keep ordinary archivist hygiene lightweight.
- Require an independent reviewer only for semantic control-plane changes.
- Reuse an existing reviewer lane instead of creating a new role.

Checklist:
- [x] Inspect current state and confirm scope.
  Acceptance criteria: the residual gap and candidate source-of-truth files are explicit.
- [x] Capture the selected direction and required files.
  Acceptance criteria: the route is specific enough to patch without relying on chat memory.
- [x] Implement the scoped changes.
  Acceptance criteria: the planned files are updated and stay coherent with the rest of the governance docs.
- [x] Run the independent review and consistency checks.
  Acceptance criteria: the new rule is reviewed and the docs pass basic consistency verification.
