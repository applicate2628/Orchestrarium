Role: `$consultant`
Goal: Write one non-blocking advisory memo for the lead on how to validate the memo-only bundle
pattern without reopening accepted bundle or scoring decisions.

Approved inputs:
- `inputs/accepted-brief.md`
- `inputs/evidence-summary.md`
- `inputs/decision-pressure.md`
- `inputs/open-questions.md`

Allowed tools:
- read the approved inputs
- edit only `candidate/advisory-memo.md`

Scope:
- recommend one direction for the near-term decision
- compare realistic alternatives and tradeoffs
- explain key risks, assumptions, uncertainty, and confidence
- keep the memo advisory-only and use the consultant provenance plus continuation contract

Out of scope:
- routing, approval, or acting as `$lead`
- implementation work, code patches, or verifier edits
- phase-plan output or new architecture ownership
- external-provider transport analysis
- new research beyond the accepted packet

Must-not-break surfaces:
- the memo-only candidate identity
- the fixed bundle contract and score-profile mapping
- the boundary between consultant advice and lead-owned routing

Expected artifact:
- one advisory memo in `candidate/advisory-memo.md`

Acceptance criteria:
- the memo is role-correct for `$consultant`
- it recommends one direction against at least two realistic alternatives
- it states uncertainty explicitly instead of pretending the evidence is complete
- it ends as non-blocking decision support with a reusable continuation prompt

Gate to next stage:
- the lead can consume the memo as decision support without mistaking it for approval, routing, or
  implementation authority
