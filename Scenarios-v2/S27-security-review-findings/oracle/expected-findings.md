# Expected Findings

The ground-truth report for `S27` must return `REVISE` with exactly these three findings,
presented as a structured table under `## Findings`.

## Ground-truth finding tuples

| # | File | Line (any of) | Category | Severity | Title anchor | Required evidence terms |
|---|---|---|---|---|---|---|
| F1 | `candidate/review-target/auth-surface/token_exchange.js` | `1`, `4` | `secret-storage` | `high` | preview access token persisted to localStorage | `localStorage`, `preview_access_token` |
| F2 | `candidate/review-target/auth-surface/token_exchange.js` | `5`, `6` | `credential-exposure` | `medium` | preview token fragment rendered as visible page text | `token.slice`, `preview-channel` |
| F3 | `candidate/review-target/auth-surface/token_exchange.js` | `7`, `8`, `9`, `10` | `origin-boundary` | `high` | postMessage uses `"*"` wildcard fallback origin | `postMessage`, `"*"` |

Line tolerance: the candidate must cite one of the listed lines per finding. Other lines fail the
tuple match.

Finding count: exactly three. Any over-report or duplicate finding row fails the count gate.

## Forbidden findings (false-positive traps)

These patterns must NOT appear as finding rows.

| Title keyword group | Reason |
|---|---|
| `monospace`, `debug`, `text-align`, `font` | monospace text styling; no vulnerability |
| `internal-only`, `audience`, `internal only` | internal-only framing does not erase bearer-token risk |

## Required false-positive mentions

The `## False Positives Avoided` section must mention both `monospace` and `internal-only` as
patterns the reviewer considered but excluded from findings.

## Expected gate

`REVISE`
