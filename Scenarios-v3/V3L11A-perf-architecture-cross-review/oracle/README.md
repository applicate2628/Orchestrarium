# Oracle

- `perf-architecture-review-contract.json` - the findings-table contract: four `file:line`-bound
  required findings, exact_finding_count, forbidden false-positive traps, required FP-boundary terms,
  and the expected gate decision.
- `expected-findings.md` / `false-positive-traps.md` / `severity-anchors.md` - human-readable rationale.
- `scoring-anchors.md` - the PASS conditions and the near-peer separation argument.
- `reference/review-report.md` - a passing reference report for the admission probe and four-probe.

Not staged to the provider-visible root. The verifier reads code only (executes nothing), so it runs
safely from the private scorer root with no `BENCH_EXEC_ROOT` exec split.
