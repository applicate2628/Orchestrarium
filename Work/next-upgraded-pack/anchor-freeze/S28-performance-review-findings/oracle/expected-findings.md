# Expected Findings

The ground-truth report for `S28` must return `REVISE` with exactly these three findings,
presented as a structured table under `## Findings`.

## Ground-truth finding tuples

| # | File | Line (any of) | Category | Severity | Title anchor | Required evidence terms |
|---|---|---|---|---|---|---|
| F1 | `candidate/review-target/cohort-packager/packager.js` | `2`, `3`, `4` | `hot-path` | `high` | full-list sort runs on every render | `sort`, `packets` |
| F2 | `candidate/review-target/cohort-packager/packager.js` | `5`, `6` | `serialization` | `medium` | each packet JSON-serialized during render | `JSON.stringify`, `packet` |
| F3 | `candidate/review-target/cohort-packager/packager.js` | `10`, `11` | `memory` | `medium` | metric history grows unbounded with serialized snapshots | `history.push`, `snapshot` |

Line tolerance: the candidate must cite one of the listed lines per finding. Other lines fail the
tuple match.

Finding count: exactly three.

## Forbidden findings (false-positive traps)

| Title keyword group | Reason |
|---|---|
| `min-height`, `static style`, `css style` | static min-height styling; not a performance bug |
| `sort once`, `load-time sort`, `one-time sort`, `initial sort` | sorting once at load-time is not itself a finding |

## Required false-positive mentions

The `## False Positives Avoided` section must mention both `min-height` and `sort once` as
patterns the reviewer considered but excluded from findings.

## Expected gate

`REVISE`
