# Closure — separate REVISE cycles from review-loop rounds

Closed: 2026-08-11T20:08:17Z

Outcome: PASS. The generic Lead correction limit and autonomous review-loop round limit now have separate named owners, exact units, and drift guards. Existing values, explicit overrides, state schema, and ledger behavior are preserved.

Evidence: durable three-class RED; cap contract 6 PASS plus 6 subtests; combined owner/dispatch slice 57 PASS plus 16 subtests; validator self-test PASS; Codex 530/530; Claude 449/449; spine 111/111; CodeGraph fresh; compile, staged boundary, publication-safety, and diff checks PASS.

Residual risk: self-contained review-loop provider bindings intentionally repeat the runtime number; the dedicated six-consumer guard makes that boundary duplication fail closed on drift. The parked p95 task remains unverified on a quiet host and is not part of this outcome.

Outcome-unmeasured: no performance metric applies; no benchmark or hot-path behavior changed.

Archive location: `work-items/archive/2026-08/2026-08-11-separate-revise-cap-contracts/`.

## Retrospective

- A deliberately broad first regex caught numbered steps as cap values; correcting the oracle before source edits prevented a false production fix.
- Full-suite QA exposed an unrelated stale archived-bug pointer. It was isolated in commit `4a3132b9`, then the cap suite was rerun from a green baseline.

## Terms and Abbreviations

- **Cycle:** one correction/re-evaluation result for the same role and artifact.
- **Round:** one complete multi-angle autonomous review iteration.
- **PASS:** all scoped gates completed without a blocking finding.
Lifecycle-schema: work-items-physical-v1
