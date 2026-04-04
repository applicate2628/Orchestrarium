# Canonical Brief

- Item: Publication-safety automation and closure artifact
- Roadmap source: [roadmap.md](roadmap.md)
- Goal: Make publication-safety checks more reliable and make completed work items closeable and archivable through a formal closure artifact.
- Scope: a repo-relative publication-safety scan/check, a `closure.md` artifact and template, closure/archive checklist updates, and task-memory documentation needed to support them.
- Out of scope: CI or pre-commit integration, binary scanning, historical repo cleanup, or unrelated workflow refactors.
- Constraints and assumptions: keep the solution publication-safe, repo-relative, lightweight, and independently shippable in two tracks so closure-artifact work does not block on scan tuning.
- Accepted extension seams: `references/`, `scripts/` or equivalent repo-relative tooling location, `work-items/templates/work-item/`, `work-items/README.md`, `work-items/index.md`, and related governance docs.
- Must-not-break surfaces: existing publication-safety policy, current stage-gate model, tracked task-memory flow, and human review before `git push`.
- Critical risks and owners: false confidence from weak scan coverage owned by `$lead`; archive-hygiene and closure-template correctness owned by `$knowledge-archivist`; maintainability of the scan path owned by the implementing toolchain lane.
- Required roles and reviewers: `$lead`, `$planner`, `$knowledge-archivist`, `$toolchain-engineer`, and reviewer lanes as needed after implementation.
- Integration owner: `$knowledge-archivist`
- Current stage: Completed
- Next stage: None
- Open blockers: None
