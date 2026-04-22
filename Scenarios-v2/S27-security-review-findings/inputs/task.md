# Security Review Task

Review the bounded auth-surface change in `candidate/review-target/auth-surface/` and produce a
findings-only security report. Identify every concrete security defect actually present in the
code; do not patch the code, do not redesign the auth flow.

## Required output shape

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
- `Line` must be a single integer — the primary line where the defect is visible in the code.
- `Category` must be one of: `secret-storage`, `credential-exposure`, `origin-boundary`, `session`.
- `Severity` must be one of: `high`, `medium`, `low`. Use `oracle/severity-anchors.md` as the
  calibration reference.
- `Title` must name the defect class in 3–8 words.
- `Evidence` must cite the specific variable, function, API, or origin value involved and briefly
  state the attack vector. Bare line quotes are not evidence.

Additional rules:

- Report every concrete defect you find; do not fabricate defects.
- Do not report cosmetic, stylistic, performance, accessibility, or UX observations — out of scope
  per `inputs/review-boundary.md`.
- Every finding must cite a real line number in the reviewed file.

### `## False Positives Avoided`

A short bullet list naming patterns you considered but chose NOT to report as findings, with a
one-line reason each. Demonstrate boundary discipline on patterns that look suspicious but are not
defects here.

### `## Gate Decision`

One line with exactly one of: `PASS`, `REVISE`, `BLOCK`.

## Scope references

- `inputs/review-boundary.md` — review scope rules
- `inputs/accepted-security-claims.md` — security invariants
- `inputs/secret-and-boundary-notes.md` — abstract secret-handling rules
- `oracle/severity-anchors.md` — severity calibration (read-only)

You must not edit `candidate/review-target/`, `inputs/`, `oracle/`, or `verifiers/`.
