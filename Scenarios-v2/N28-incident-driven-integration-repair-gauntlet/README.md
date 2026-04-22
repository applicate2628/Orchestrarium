# N28 Incident-Driven Integration Repair Gauntlet

`N28` combines implementation repair with incident-source reconciliation. The task requires a
coherent patch across configuration, intake normalization, semantic dedupe, dependency planning,
cycle handling, policy scheduling, crash/resume idempotency, rollback, audit trace, and reporting,
plus a source-bound reconciliation note that rejects stale requirements and answers review feedback.

The binary verifier remains strict. A separate post-run scorer under `Work/next-upgraded-pack/Tooling`
computes rubric/time/cost/patch-quality/reconciliation metrics from run roots after execution.
