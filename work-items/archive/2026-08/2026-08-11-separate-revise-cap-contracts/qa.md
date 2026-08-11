# QA — REVISE cap contract separation

Gate: PASS

## Results

- Durable RED matched the three accepted defect classes; the preservation row passed after its own regex correction.
- Final cap contract: 6 PASS plus 6 subtests.
- Full cap/review-loop/dispatch slice: 57 PASS plus 16 subtests.
- Validator self-test, Python compile, diff check, Codex 530/530, Claude 449/449, and spine 111/111 all PASS.
- Exact documentation scan finds the generic numeric declaration only in `shared/AGENTS.shared.md`; review-loop hard-boundary duplicates all equal the runtime owner.
- Staged name-status excludes every parked p95 implementation/test/doc path. `RELEASE_NOTES.md` stages only the cap bullet.

## Residuals

No cap behavior residual. The p95 task remains parked and unverified on a quiet host. The separate stale lifecycle prerequisite was fixed in `4a3132b9` and is not part of this gate.

## Terms and Abbreviations

- **QA:** quality assurance.
- **PASS:** scoped checks completed without a blocking finding.
