# Expected Verdict

The correct QA gate decision is `REVISE`.

## Acceptance mapping truth

- `AC1` passes. `inputs/executed-checks.md` shows the targeted tests passed and JSON mode emitted
  the required `status`, `generated_at`, and `items` keys.
- `AC2` fails. `inputs/executed-checks.md` shows `--dry-run --json` still created
  `status.snapshot.json`, and `inputs/bounded-diff.patch` shows the write happens before the
  `dry_run` branch returns.
- `AC3` is not evidenced. `inputs/nearby-smoke-coverage.md` records the legacy
  `--text-summary` smoke as `NOT RUN`, so the nearby must-not-break surface remains unverified.
- `AC4` passes. `inputs/performance-smoke.md` records a `1.41s` average against a `2.0s` budget.

## Correct QA read

- the dry-run failure is a real product regression, not just a missing assertion
- the missing nearby smoke is a verification gap that should hold the gate even though it is not
  the same defect as the dry-run regression
- the performance smoke is adequate and should not be raised as a blocker
- the report should stay in QA scope and should not turn into a repair plan or architecture review
