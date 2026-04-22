# N27 Release Train Governor Long-Horizon Repeat Gauntlet

`N27` repeats the long-horizon integration signal on a new deploy-train governance domain. The task
requires a coherent patch across configuration, intake normalization, semantic dedupe, dependency
planning, cycle handling, policy scheduling, crash/resume idempotency, exactly-once notifications,
rollback, audit trace, and reporting.

The binary verifier remains strict. A separate post-run scorer under `Work/next-upgraded-pack/Tooling`
computes rubric/time/cost/patch-quality metrics from run roots after execution.
