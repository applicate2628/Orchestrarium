# Decoy Map

Reject these as primary findings:

- `FP1-json-serialization-hotpath`: JSON output is not in the quote hot path measured here.
- `FP2-decimal-rounding`: rounding is deterministic and not the performance or correctness defect.
- `FP3-markdown-report-format`: markdown wording in `perf-summary.md` is not a hot-path blocker.

Reject stale source:

- `candidate/review-target/docs/stale-ops-assumptions.md`
- `single-region-only`
- `caller-normalizes-feature-flags`
- `warm-cache-speedup-is-production-speedup`
