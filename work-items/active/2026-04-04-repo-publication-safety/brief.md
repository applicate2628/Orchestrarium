# Canonical Brief

- Item: Repo publication safety
- Roadmap source: [roadmap.md](roadmap.md)
- Goal: Make tracked repository content safe for publication by default.
- Scope: Repo-wide publication-safety policy, local-only scratch boundary, and documentation links.
- Out of scope: Automated scanning or code changes outside docs and ignore configuration.
- Constraints and assumptions: Keep tracked artifacts publication-safe; prefer repo-relative paths and redacted summaries.
- Accepted extension seams: `references/`, `work-items/`, root `.gitignore`, and repo-level docs.
- Must-not-break surfaces: Canonical task memory in `work-items/` and the existing lead routing model.
- Critical risks and owners: Leakage risk owned by `$lead` and `$knowledge-archivist`.
- Required roles and reviewers: `$knowledge-archivist` for hygiene, `$lead` for gate acceptance.
- Integration owner: `$knowledge-archivist`
- Current stage: Completed
- Next stage: Archive or follow-up automation if separately admitted
- Open blockers: None
