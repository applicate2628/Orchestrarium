# Oracle

The oracle material defines the ground-truth review outcome for `N03`.

## Review truth

The bounded change should not pass generic pre-PR review. The correct gate decision is `REVISE`
because the helper drops `added` and `renamed` paths, collapses distinct findings by title alone,
and silently hides malformed hunk headers by returning empty evidence.

## Included oracle files

- `generic-review-contract.json` provides machine-readable bundle and report anchors
- `expected-findings.md` lists the required findings and their intended severity
- `severity-anchors.md` defines the severity scale for this review bundle
- `false-positive-traps.md` documents tempting but incorrect architecture, security, and
  performance-adjacent findings
- `scoring-anchors.md` maps strong and weak `N03` runs
