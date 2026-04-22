# N16 Release Lane Integration Gauntlet

`N16` benchmarks long-horizon integration work across a release-lane pipeline. The task requires a
coherent patch across configuration, intake normalization, semantic dedupe, dependency planning,
freeze scheduling, idempotent ledger writes, exactly-once notifications, rollback, audit trace, and
reporting.

The binary verifier remains strict. A separate post-run scorer under `Work/next-upgraded-pack/Tooling`
computes rubric/time/cost/patch-quality metrics from run roots after execution.
