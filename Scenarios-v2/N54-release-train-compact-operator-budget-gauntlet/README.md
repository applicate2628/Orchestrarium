# N54 Release Train Compact Operator-Budget Gauntlet

`N54` repeats the N27 long-horizon integration signal on a deploy-train governance domain, with a
visible compactness gate. The task requires a coherent patch across configuration, intake
normalization, semantic dedupe, dependency planning, cycle handling, policy scheduling,
crash/resume idempotency, exactly-once notifications, rollback, audit trace, and reporting.

The binary verifier remains strict and now includes `../meta/worker-output.txt <= 40000` as a
scoreable operator-output budget. A separate post-run scorer under
`Work/next-upgraded-pack/Tooling` computes rubric/time/cost/patch-quality metrics from run roots
after execution.
