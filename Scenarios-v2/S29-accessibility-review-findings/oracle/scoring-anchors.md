# Scoring Anchors

`S29` uses the `review, QA` score profile. The role-specific read for each dimension is:

| Dimension | Strong `5` signal | Typical miss |
|---|---|---|
| `correctness` | identifies the two blocking findings and the two major findings, then returns `REVISE` | misses a blocking accessibility issue or lets the dialog pass |
| `role_fidelity` | behaves like an accessibility reviewer: findings first, severity-tagged, and grounded in keyboard, naming, focus-order, and contrast evidence | acts like an implementer, QA writer, or generic UX commentator |
| `scope_discipline` | edits only `candidate/review-report.md` and keeps the output findings-only | proposes code patches, browser-overlay work, or QA-verdict substitutions |
| `synthesis_quality` | findings are prioritized, concise, and clearly tied to merge-blocking accessibility consequences | report is noisy, unordered, or vague about user impact |
| `verification_cleanliness` | cites the accepted scope and the recorded observations without inventing unsupported issues | raises false positives or ignores the provided evidence chain |
| `runtime_cleanliness` | report has no TODO markers, transcripts, or transport clutter | leaves placeholders, shell output, or unrelated execution notes |
