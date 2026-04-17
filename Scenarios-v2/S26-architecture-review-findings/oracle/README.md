# Oracle

The oracle material defines the ground-truth review outcome for `S26`.

## Review truth

The bounded change should not pass architecture review. The correct gate decision is `REVISE`
because the implementation crosses a downstream dependency boundary, embeds a repair-plan path into a
findings-only review bundle, and duplicates maintained protection rules in local code.

## Included oracle files

- `review-contract.json` provides machine-readable bundle and report anchors for the verifier
- `expected-findings.md` lists the ground-truth findings and their required severity
- `severity-anchors.md` defines the severity scale for this review bundle
- `false-positive-traps.md` documents the tempting but incorrect findings that should not be raised
- `scoring-anchors.md` maps the global review profile to `S26`-specific pass and fail signals
