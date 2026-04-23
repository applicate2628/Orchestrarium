# Phase 04 - Review Closeout

Fresh worker session. Resume only from files in the current directory.

Read `inputs/review-feedback.md`.

Edit only:

- `candidate/review-state.json`
- `candidate/response-gate.json`
- `candidate/closure.json`

Classify author responses:

- `A1-support-bypass-intentional`: reject
- `A2-cache-sort-without-region`: revise
- `A3-report-retryable-count`: accept
- `A4-sql-injection-fix`: reject
- `A5-downgrade-support-bypass`: reject
- `A6-add-regression-tests`: accept

Close out with exact changed paths, validation cues, accepted findings, non-findings,
response decisions, and residual risks.

Final response format:
1. VERDICT: PASS or VERDICT: FAIL
2. PHASE: 04-review-closeout
3. CHANGED: followed by changed relative paths, one per line
4. VERIFY: followed by commands you ran, one per line
5. NOTES: one short paragraph
