# Task Memory Governance Plan

Status note:
- External consultant invocation was attempted on 2026-04-04.
- The run failed with a quota-limit message before producing a usable advisory memo.
- The repository task-memory migration continues locally in this workspace.

Selected direction:
- keep a dedicated tracked work-item store instead of relying on the ignored legacy `.plans/` directory
- add a structured `active/`, `archive/`, `templates/`, and `index.md` layout inside `work-items/`
- make `roadmap.md`, `brief.md`, and `status.md` mandatory for lead-routed non-trivial work
- make `plan.md` mandatory before implementation or review starts
- assign content ownership to the producing role and structure ownership to `$knowledge-archivist`

Checklist:
- [x] Audit the current artifact and documentation behavior in the repo.
  Acceptance criteria: the existing source-of-truth docs, `.plans/` layout, and failure mode are explicit.
- [x] Attempt optional external consultation before workspace edits.
  Acceptance criteria: the attempt and its outcome are recorded.
- [x] Add the canonical task-memory structure and templates under `work-items/`.
  Acceptance criteria: active work, archive, templates, and the recovery entry point are explicit.
- [x] Update repo policy and operating-model docs to require and describe the new task-memory rules.
  Acceptance criteria: storage location, owners, mandatory artifacts, and recovery rules are documented in the source-of-truth docs.
- [x] Verify links and summarize the enforced workflow.
  Acceptance criteria: the new docs point to the same canonical model and the recovery workflow is clear.
