# Accessibility Review Task

Review the bounded dialog implementation in `candidate/review-target/share-dialog/` and produce a
findings-only accessibility report. Identify every concrete accessibility defect actually present
in the code; do not patch the dialog, do not request a browser harness.

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
- `Line` must be a single integer — the primary line where the defect is visible.
- `Category` must be one of: `keyboard`, `semantic-labeling`, `focus-order`, `contrast`, `at-exposure`, `aria`, `focus`.
- `Severity` must be one of: `blocking`, `major`, `minor`. Use `oracle/severity-anchors.md`.
- `Title` must name the defect class in 3–8 words.
- `Evidence` must cite the specific element, attribute, or CSS property involved and briefly
  state the assistive-technology or keyboard consequence.

Additional rules:

- Report every concrete defect you find; do not fabricate defects.
- Do not report cosmetic, stylistic, performance, security, or UX-only observations.
- Every finding must cite a real line number in the reviewed file.
- Prioritize findings by severity. All five ground-truth defects must be captured.

### `## False Positives Avoided`

A short bullet list naming patterns you considered but chose NOT to report as findings, with a
one-line reason each.

### `## Gate Decision`

One line with exactly one of: `PASS`, `REVISE`, `BLOCK`.

## Scope references

- `inputs/review-boundary.md` — review scope rules
- `inputs/accepted-accessibility-scope.md` — accessibility scope
- `inputs/contrast-and-focus-notes.md` — contrast thresholds for this gate
- `oracle/severity-anchors.md` — severity calibration (read-only)

You must not edit `candidate/review-target/`, `inputs/`, `oracle/`, or `verifiers/`.
