# N51 Systems Turnaround-Budget Hotfix

This diagnostic bundle hardens the systems/toolchain signal from `N19` and `N24` with an
immutable-CI constraint, a compact operator-output budget, and a first-class turnaround SLA.
The worker must repair the artifact-staging implementation without changing the visible test
baseline, protected API/model files, stale docs, or legacy helpers.

The candidate must repair only the editable production implementation files named in
`scenario.yaml`. Hidden verifier probes own correctness; editing visible tests, exceeding
`../meta/worker-output.txt <= 40000`, or exceeding `360s` from prompt to worker-output write is a
scoreable failure in this lane.
