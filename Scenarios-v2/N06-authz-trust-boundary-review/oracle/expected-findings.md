# Expected Findings

The ground-truth report for `N06` must return `REVISE` with exactly these three findings, in
severity order, presented as a structured table under `## Findings`.

## Ground-truth finding tuples

| # | File | Line (any of) | Category | Severity | Title anchor | Required evidence terms |
|---|---|---|---|---|---|---|
| F1 | `candidate/review-target/access-surface/grant_console.js` | `2`, `7` | `authz` | `high` | query-string `reviewerRole` as authorization gate | `reviewerRole`, `params` |
| F2 | `candidate/review-target/access-surface/grant_console.js` | `27`, `28`, `29` | `trust-boundary` | `high` | parent-window `payload.trusted` trust break | `payload.trusted`, `effectiveTenant` |
| F3 | `candidate/review-target/access-surface/grant_console.js` | `15`, `18`, `19` | `authz` or `replay` | `medium` | client-chosen authority forwarded to server | `X-Reviewer-Role`, `tenantId` |

Line tolerance: the candidate must cite one of the listed lines per finding. Other lines fail the
tuple match.

Finding count: exactly three. Any over-report or duplicate finding row fails the count gate.

## Forbidden findings (false-positive traps)

These patterns must NOT appear as finding rows. If a candidate row's title matches any of these
keyword groups, the verifier fails.

| Title keyword group | Reason |
|---|---|
| `policy.css`, `opacity`, `cosmetic`, `css` | CSS decoration only; no security impact |
| `disabled button`, `approve-grant disabled`, `button disabled` | client-side UI hint; not an authz boundary |

## Required false-positive mentions

The `## False Positives Avoided` section must mention both `disabled button` and `policy.css` as
patterns the reviewer considered but excluded from findings. This demonstrates boundary discipline.

## Expected gate

`REVISE`
