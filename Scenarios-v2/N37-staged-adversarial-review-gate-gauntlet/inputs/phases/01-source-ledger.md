# Phase 01 - Source Ledger

Fresh worker session. Read `README.md`, `candidate/README.md`, `scenario.yaml`,
`inputs/task.md`, and `inputs/decoy-map.md`.

Edit only `candidate/review-state.json`.

Record:

- phase id `01-source-ledger`
- plan fingerprint `n37-staged-review-adr-v1`
- accepted source IDs `S1` through `S12`
- stale-source rejections for the stale review notes and stale assumptions
- false-positive traps for SQL injection, `audit_label` secret leakage, and zero TTL
- exact patch budget paths expected for final closeout
- owners for source arbitration, ADR decision, review findings, response gate, and closure

Do not edit findings, ADR, response, closure, or review-target files in this phase.

Final response format:
1. VERDICT: PASS or VERDICT: FAIL
2. PHASE: 01-source-ledger
3. CHANGED: followed by changed relative paths, one per line
4. VERIFY: followed by commands you ran, one per line
5. NOTES: one short paragraph
