# Canonical Brief

- Item: Periodic control matrix
- Roadmap source: [roadmap.md](roadmap.md)
- Goal: Close the gap between existing stage gates and missing periodic controls in the repository workflow.
- Scope: Define a minimal-but-rigorous periodic control matrix, document it canonically, and connect it to repo-level guidance.
- Out of scope: Automation, CI enforcement, new runtime tooling, or broad role redesign.
- Constraints and assumptions: Keep the solution publication-safe, repo-relative, and lightweight enough for humans to run without turning the workflow into bureaucracy.
- Accepted extension seams: `references/`, repo-level docs, and `work-items/` task memory.
- Must-not-break surfaces: Existing stage-gate model, work-item recovery flow, and repo-wide publication-safety contract.
- Critical risks and owners: Process drift and stale items owned by `$lead`; repository hygiene drift owned by `$knowledge-archivist`; maintainability drift owned by `$architecture-reviewer`.
- Required roles and reviewers: `$lead`, `$knowledge-archivist`, `$architecture-reviewer`, and required Claude deep-review through `$consultant`.
- Integration owner: `$lead`
- Current stage: Planning
- Next stage: Documentation update and validation
- Open blockers: None
