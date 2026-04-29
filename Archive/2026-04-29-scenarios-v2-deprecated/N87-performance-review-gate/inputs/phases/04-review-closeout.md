# Phase 04 - Review Closeout

Fresh worker session. Resume only from files in the current directory.

Read `inputs/review-feedback.md`.

Edit only:

- `candidate/review-state.json`
- `candidate/response-gate.json`
- `candidate/closure.json`

Classify author responses:

- `A1-approve-warm-only-speedup`: reject
- `A2-cache-key-sku-only`: reject
- `A3-add-region-only`: revise
- `A4-raise-memory-budget`: reject
- `A5-add-cold-mixed-benchmark`: accept
- `A6-bound-cache-lifetime`: accept

Close out with exact changed paths, validation cues, accepted findings, non-findings,
response decisions, residual risks, and final gate decision `REVISE`.

Final response format:
1. VERDICT: PASS or VERDICT: FAIL
2. PHASE: 04-review-closeout
3. CHANGED: followed by changed relative paths, one per line
4. VERIFY: followed by commands you ran, one per line
5. NOTES: one short paragraph
