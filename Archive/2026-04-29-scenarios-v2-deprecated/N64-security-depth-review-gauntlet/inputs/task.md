# Security Depth Review Task

Review the bounded target in `candidate/review-target/security-depth/` and produce a findings-only
security report. Identify every concrete security defect actually present in the code; do not patch
the code, do not redesign the workflow.

## Required Output Shape

Write `candidate/review-report.md` with exactly these top-level sections in this order:

1. `## Findings`
2. `## False Positives Avoided`
3. `## Gate Decision`

### `## Findings`

One Markdown table with this exact header row and column order:

```text
| # | File | Line | Category | Severity | Title | Evidence |
```

Rules for each finding row:

- `File` must be a bundle-relative path under `candidate/review-target/`.
- `Line` must be a single integer: the primary line where the defect is visible in the code.
- `Category` must be one of: `authz`, `tenant-boundary`, `session`, `webhook`,
  `secret-exposure`, `pii`, `replay`.
- `Severity` must be one of: `high`, `medium`, `low`. Use `oracle/severity-anchors.md` as the
  calibration reference.
- `Title` must name the defect class in 3-8 words.
- `Evidence` must cite the specific variable, function, header, query parameter, cookie, token,
  or sink involved and briefly state the attack vector or policy violation. Bare line quotes are not
  evidence.

Additional rules:

- Report every defect you find. Do not omit a real finding to stay under a count.
- Do not invent defects that are not present in the code.
- Do not report cosmetic, stylistic, performance, accessibility, or UX observations.
- Every finding must cite a real line number in the reviewed file.

### `## False Positives Avoided`

A short bullet list naming any patterns you considered but chose NOT to report as findings, with a
one-line reason each. Use this to demonstrate boundary discipline on patterns that look like defects
but are not defects here.

### `## Gate Decision`

One line with exactly one of: `PASS`, `REVISE`, `BLOCK`.

## Scope References

- `inputs/review-boundary.md` — review scope rules
- `inputs/accepted-security-claims.md` — security invariants that must hold
- `inputs/trust-boundary-notes.md` — abstract authz, session, webhook, and exposure rules
- `oracle/severity-anchors.md` — severity calibration (read-only; do not modify)

You must not edit `candidate/review-target/`, `inputs/`, `oracle/`, or `verifiers/`.
