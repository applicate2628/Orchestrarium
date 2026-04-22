# Performance Review Task

Review the bounded cohort-packager target in `candidate/review-target/cohort-packager/` and produce
a findings-only performance report. Identify every concrete latency or memory defect actually
present in the code; do not patch the code, do not redefine the accepted budgets.

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
- `Category` must be one of: `hot-path`, `serialization`, `memory`, `latency`.
- `Severity` must be one of: `high`, `medium`, `low`. Use `oracle/severity-anchors.md` as the
  calibration reference.
- `Title` must name the defect class in 3–8 words.
- `Evidence` must cite the specific function, API, or call involved and briefly state why it is
  a latency or memory risk under sustained use. Bare line quotes are not evidence.

Additional rules:

- Report every concrete defect you find; do not fabricate defects.
- Do not report cosmetic, stylistic, security, accessibility, or UX observations — out of scope
  per `inputs/review-boundary.md`.
- Every finding must cite a real line number in the reviewed file.

### `## False Positives Avoided`

A short bullet list naming patterns you considered but chose NOT to report as findings, with a
one-line reason each.

### `## Gate Decision`

One line with exactly one of: `PASS`, `REVISE`, `BLOCK`.

## Scope references

- `inputs/review-boundary.md` — review scope rules
- `inputs/accepted-performance-budgets.md` — performance envelope
- `inputs/latency-and-memory-notes.md` — abstract perf-pattern rules
- `oracle/severity-anchors.md` — severity calibration (read-only)

You must not edit `candidate/review-target/`, `inputs/`, `oracle/`, or `verifiers/`.
