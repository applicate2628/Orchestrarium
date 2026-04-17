# S06 Task

Produce one factual research memo that answers the following questions from the bundle-local repo
slice:

1. Which files and symbols currently determine which scenario bundles are loaded for a requested
   surface ID?
2. Where does the active `score_profile` come from when a result row is written?
3. What evidence shows whether archived v1 scenario material is still part of the live path or
   only retained as historical reference?
4. Which claims in the noisy notes are false leads in the visible slice?
5. What remains unknown because the bounded slice does not include the relevant caller or runtime
   surface?

## Output contract

- Edit only `candidate/repository-fact-memo.md`.
- Cite evidence with forward-slash relative paths and line numbers, for example
  `candidate/repo-snapshot/benchmarks/runner/collect_scenarios.py:10`.
- Keep the memo factual. Do not include recommendations, design choices, phase plans, or code
  changes.
- Separate confirmed facts, false leads, and unknowns explicitly.
- End with one gate decision: `PASS`, `REVISE`, or `BLOCKED`.
