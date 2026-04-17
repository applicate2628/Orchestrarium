# Inputs

This directory is the immutable packet for the `S26` architecture review scenario.

## Included materials

- `task.md` defines the review-only task contract and the expected report shape
- `accepted-design.md` is the accepted design packet with the claims list to verify
- `repo-context.md` captures the relevant ownership boundaries and local standards
- `known-risks.md` identifies the non-style risks already known about this phase
- `bounded-diff.patch` is the review diff for the changed files under `candidate/review-target/`

These inputs are review-specific. They are intentionally written so a generic code-review answer or
an implementation patch plan will miss the architecture boundary, severity, or false-positive
requirements.
