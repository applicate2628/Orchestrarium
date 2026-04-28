# Phase 01 - Source Ledger

Fresh worker session. Read `README.md`, `candidate/README.md`, `scenario.yaml`,
`inputs/task.md`, and `inputs/decoy-map.md`.

Edit only `candidate/review-state.json`.

Record:

- phase id `01-source-ledger`
- plan fingerprint `n87-performance-review-gate-v1`
- accepted source IDs `S1` through `S12`
- stale-source rejections for the stale ops assumptions and warm-only production-speedup claim
- false-positive traps for JSON serialization, decimal rounding, and markdown report format
- exact review artifact paths expected for final closeout
- owners for source arbitration, performance ADR, review findings, response gate, and closure

Do not edit findings, ADR, response, closure, or review-target files in this phase.

Final response format:
1. VERDICT: PASS or VERDICT: FAIL
2. PHASE: 01-source-ledger
3. CHANGED: followed by changed relative paths, one per line
4. VERIFY: followed by commands you ran, one per line
5. NOTES: one short paragraph
