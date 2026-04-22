# Scalability And Maintainability Cross-Review Task

Review the bounded routing-matrix target in `candidate/review-target/routing-matrix/` and produce
a findings-only cross-review report. Identify every concrete scalability or maintainability defect
actually present in the code; do not patch the code, do not redefine the accepted constraints.

## Required output shape

Write `candidate/review-report.md` with exactly these top-level sections in this order:

1. `## Findings`
2. `## False Positives Avoided`
3. `## Maintainability Notes`
4. `## Gate Decision`

### `## Findings`

One Markdown table with this exact header row and column order:

```text
| # | File | Line | Category | Severity | Title | Evidence |
```

Rules for each finding row:

- `File` must be a bundle-relative path under `candidate/review-target/`.
- `Line` must be a single integer — the primary line where the defect is visible in the code.
- `Category` must be one of: `scalability`, `maintainability`, `memory`, `architecture`.
- `Severity` must be one of: `blocking`, `major`, `minor`. Use `oracle/severity-anchors.md`.
- `Title` must name the defect class in 3–8 words.
- `Evidence` must cite the specific function, structure, or call involved and briefly state the
  scalability or maintainability risk.

Additional rules:

- Report every concrete defect you find; do not fabricate defects.
- Do not report cosmetic, stylistic, security, accessibility, or UX observations.
- Every finding must cite a real line number in the reviewed file.

### `## False Positives Avoided`

A short bullet list naming patterns you considered but chose NOT to report as findings, with a
one-line reason each.

### `## Maintainability Notes`

Short maintainability observations that are not themselves findings — context the next reviewer
should know.

### `## Gate Decision`

One line with exactly one of: `PASS`, `REVISE`, `BLOCK`.

## Scope references

- `inputs/review-boundary.md` — review scope rules
- `inputs/accepted-review-constraints.md` — accepted constraints
- `inputs/scalability-notes.md` — abstract scalability rules
- `oracle/severity-anchors.md` — severity calibration (read-only)

You must not edit `candidate/review-target/`, `inputs/`, `oracle/`, or `verifiers/`.
