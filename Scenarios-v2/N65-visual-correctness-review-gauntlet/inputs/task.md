# Visual Correctness Review Task

Review the bounded target in `candidate/review-target/visual-ui/` and produce a findings-only
visual correctness report. Identify every concrete UI visual defect actually supported by the DOM,
CSS, state matrix, and screenshot probes; do not patch the code, do not redesign the UI.

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
- `Line` must be a single integer: the primary source line where the visual defect is caused or made visible.
- `Category` must be one of: `layout`, `responsive`, `state`, `contrast`, `focus`,
  `occlusion`, `affordance`, `motion`.
- `Severity` must be one of: `high`, `medium`, `low`. Use `oracle/severity-anchors.md` as the
  calibration reference.
- `Title` must name the visual defect class in 3-8 words.
- `Evidence` must cite a concrete selector, state, CSS property, or screenshot probe ID and briefly
  state the observed user impact. Bare line quotes are not evidence.

Additional rules:

- Report every defect you find. Do not omit a real finding to stay under a count.
- Do not invent defects that are not supported by the target evidence.
- Do not report code style, architecture, performance, accessibility-only, or copywriting issues.
- Every finding must cite a real line number in the reviewed file.

### `## False Positives Avoided`

A short bullet list naming patterns you considered but chose NOT to report as findings, with a
one-line reason each. Use this to demonstrate boundary discipline on harmless visual details.

### `## Gate Decision`

One line with exactly one of: `PASS`, `REVISE`, `BLOCK`.

## Scope References

- `inputs/review-boundary.md` - review scope rules
- `inputs/visual-acceptance-notes.md` - accepted visual invariants
- `inputs/probe-method.md` - how screenshot evidence should be interpreted
- `oracle/severity-anchors.md` - severity calibration (read-only; do not modify)

You must not edit `candidate/review-target/`, `inputs/`, `oracle/`, or `verifiers/`.
