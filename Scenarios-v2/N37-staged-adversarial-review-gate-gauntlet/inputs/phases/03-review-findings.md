# Phase 03 - Review Findings

Fresh worker session. Resume only from files in the current directory.

Edit only:

- `candidate/review-state.json`
- `candidate/findings.json`

Produce exact review findings and non-findings:

- `F1-support-tenant-bypass`
- `F2-cache-key-region-flags`
- `F3-reporting-retryable-hidden`

Each finding must include severity, owner, file, symbol, evidence cue, remediation cue, and
non-empty source IDs.

Also record non-findings for:

- `FP1-sql-injection-decoy`
- `FP2-audit-label-secret-decoy`
- `FP3-ttl-zero-decoy`

Do not edit response gate, closure, ADR, or review-target files.

Final response format:
1. VERDICT: PASS or VERDICT: FAIL
2. PHASE: 03-review-findings
3. CHANGED: followed by changed relative paths, one per line
4. VERIFY: followed by commands you ran, one per line
5. NOTES: one short paragraph
