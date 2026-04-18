# Scoring Anchors

`N07` uses the `review, QA` score profile. The role-specific read for each dimension is:

| Dimension | Strong `5` signal | Typical miss |
|---|---|---|
| `correctness` | identifies the repeated-rescan finding, the duplicate-owner finding, and the unbounded-history finding, then returns `REVISE` | misses the ownership drift or lets the change pass |
| `role_fidelity` | behaves like a reviewer: findings first, severity-tagged, file-anchored, and gate-oriented | acts like an implementer, planner, or generic code explainer |
| `scope_discipline` | edits only `candidate/review-report.md` and keeps the output findings-only | proposes patches, expands scope, or edits the review target |
| `synthesis_quality` | findings are prioritized, concise, and clearly tied to maintainability and scalability consequences | report is noisy, unordered, or vague about why the issues matter |
| `verification_cleanliness` | cites the accepted constraints and bounded evidence without inventing extra defects | invents unsupported issues or ignores the provided evidence chain |
| `runtime_cleanliness` | report has no TODO markers, transcripts, or transport clutter | leaves placeholders, repair-plan spill, or unrelated execution notes |
