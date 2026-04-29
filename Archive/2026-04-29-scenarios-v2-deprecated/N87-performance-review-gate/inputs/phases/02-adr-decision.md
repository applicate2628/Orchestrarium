# Phase 02 - ADR Decision

Fresh worker session. Resume only from files in the current directory.

Edit only:

- `candidate/review-state.json`
- `candidate/decision-adr.md`

Write a source-bound ADR that chooses the current review stance:

- reject warm-only benchmark as production speedup evidence
- include region and sorted feature flags in price-cache identity
- bound cache lifetime across catalog refreshes
- require cold-cache mixed-context reruns and memory-retention validation before approval
- reject stale ops assumptions as non-authoritative

Update `candidate/review-state.json` with phase id `02-adr-decision` and ADR markers.

Do not edit review findings, response gate, closure, or review-target files.

Final response format:
1. VERDICT: PASS or VERDICT: FAIL
2. PHASE: 02-adr-decision
3. CHANGED: followed by changed relative paths, one per line
4. VERIFY: followed by commands you ran, one per line
5. NOTES: one short paragraph
