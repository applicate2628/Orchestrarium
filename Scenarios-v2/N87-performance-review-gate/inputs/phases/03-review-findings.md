# Phase 03 - Review Findings

Fresh worker session. Resume only from files in the current directory.

Edit only:

- `candidate/review-state.json`
- `candidate/findings.json`

Produce exact review findings and non-findings:

- `F1-warm-cache-benchmark-contamination`
- `F2-cache-key-context-loss`
- `F3-global-cache-lifetime-growth`
- `F4-approval-gate-incomplete`

Each finding must include severity, owner, file, symbol, evidence cue, remediation cue, and
non-empty source IDs.

Also record non-findings for:

- `FP1-json-serialization-hotpath`
- `FP2-decimal-rounding`
- `FP3-markdown-report-format`

Do not edit response gate, closure, ADR, or review-target files.

Final response format:
1. VERDICT: PASS or VERDICT: FAIL
2. PHASE: 03-review-findings
3. CHANGED: followed by changed relative paths, one per line
4. VERIFY: followed by commands you ran, one per line
5. NOTES: one short paragraph
