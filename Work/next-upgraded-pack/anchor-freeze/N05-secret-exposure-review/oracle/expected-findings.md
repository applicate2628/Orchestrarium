# Expected Findings

The ground-truth report for `N05` must return `REVISE` with exactly these three findings,
presented as a structured table under `## Findings`.

## Ground-truth finding tuples

| # | File | Line (any of) | Category | Severity | Title anchor | Required evidence terms |
|---|---|---|---|---|---|---|
| F1 | `candidate/review-target/exposure-surface/export_panel.js` | `2`, `3`, `4` | `url-exposure` | `high` | export token placed in download URL | `export_token`, `export-download` |
| F2 | `candidate/review-target/exposure-surface/export_panel.js` | `9`–`16` | `telemetry` | `high` | telemetry beacon ships raw token and customer email | `sendBeacon`, `exportToken` |
| F3 | `candidate/review-target/exposure-surface/export_panel.js` | `7` | `visible-secret` | `medium` | raw customer addresses rendered in visible audience panel | `customerEmails`, `masked-audience` |

Line tolerance: the candidate must cite one of the listed lines per finding.

Finding count: exactly three.

## Forbidden findings (false-positive traps)

| Title keyword group | Reason |
|---|---|
| `noopener`, `rel=noopener`, `hardening rel` | `rel=noopener` is acceptable hardening, not a vulnerability |
| `policy.css`, `monospace`, `css style` | monospace styling in `policy.css` has no security impact |

## Required false-positive mentions

The `## False Positives Avoided` section must mention both `rel="noopener"` and `policy.css`.

## Expected gate

`REVISE`
