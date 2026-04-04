# Roadmap Decision Package

- Date: 2026-04-04
- Item: Governance control-plane review gate
- Admission source: Direct human request to continue after the first four governance fixes and close the residual gap around `knowledge-archivist` as a control-plane role without an independent checker
- Intended outcome: semantic governance changes produced by `$knowledge-archivist` have an explicit independent checker, while hygiene-only changes stay lightweight
- Rationale: the current model protects builder vs blocker separation in code and publication, but still lets repository control-plane semantics drift through archivist-owned docs without a dedicated independent gate
- Success signals:
  - the rule clearly distinguishes semantic control-plane changes from hygiene-only edits
  - semantic control-plane changes route through `$architecture-reviewer`
  - ordinary archive/index/link/formatting work remains lightweight
- Scope: repo-level governance docs and tracked item state needed to define the new gate and its routing trigger
- Non-goals:
  - creating a new reviewer role
  - redesigning the whole archivist contract
  - changing product or code-delivery flows beyond the new governance gate
- Dependencies: current governance docs, Claude second opinion on the narrowest safe patch, and consistency with the first-four remediation package
- Admission decision: `delivery`
- Owner: `$lead`
