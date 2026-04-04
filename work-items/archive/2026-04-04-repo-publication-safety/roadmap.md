# Roadmap Decision Package

- Date: 2026-04-04
- Item: Repo publication safety
- Admission source: Direct human request to make tracked repository content safe for public git
- Intended outcome: Establish a repo-wide publication-safety contract, an ignored local scratch boundary, and tracked documentation links so accidental leakage is less likely.
- Rationale: The repository already keeps task memory in tracked git, so the safety boundary must cover all tracked content, not only `work-items/`.
- Success signals: A repo-wide policy exists, root ignore files define local scratch space, and the main repository docs point to the safety contract.
- Scope: Root `.gitignore`, repo-wide publication-safety reference, and documentation links in the repo-level guidance and task-memory docs.
- Non-goals: Automated secret scanning, runtime enforcement, or product code changes.
- Dependencies: Existing task-memory policy and the current repository documentation layout.
- Admission decision: `delivery`
- Owner: `$lead`
