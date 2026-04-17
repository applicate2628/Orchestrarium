# S13 Performance Engineer Bottleneck-Budget Package

`S13` benchmarks `R13 $performance-engineer` on a non-web, evidence-heavy budget and bottleneck
analysis task. The candidate is asked to produce one performance constraint package for a local
benchmark cohort packager that stages redacted replay packets for author dry runs and release
rehearsals. The package must turn the supplied traces into explicit budgets, bottleneck framing,
measurement strategy, and tradeoff boundaries before any implementation or review work begins.

## Scenario summary

The proposed `cohort-packet-packager` is a workstation and CI-only CLI flow:

1. enumerate the admitted `Scenarios-v2/` roots for a named cohort
2. copy the immutable scenario packet into a staging area
3. compute a hash manifest for every staged file
4. write a redacted replay packet and compressed archive per scenario
5. emit a cohort summary for later local replay and review

The evidence packet shows that the current draft misses the author-loop latency target, overruns
its memory ceiling during the release-sized cohort, and blurs cold-run versus warm-run behavior.
The task is not to repair the packager. The task is to define the performance constraints that
later planning and review must respect.

All materials in this bundle are synthetic and local to the repository.

## Expected candidate work

Edit only `candidate/performance-constraint-package.md`.

Use the evidence packet in `inputs/` to produce a performance-engineer artifact with:

- a concise system and workload summary
- explicit quantitative budgets
- bottleneck framing tied to observed traces
- a measurement strategy that separates cold and warm runs
- tradeoff boundaries that preserve determinism and redaction fidelity
- required constraints for later implementation planning
- explicit evidence gaps
- numbered claims and a final gate decision

## What this bundle tests

- performance-constraint definition instead of generic optimization advice
- bottleneck reasoning grounded in stage-level evidence
- measurement discipline with explicit latency, memory, and variance handling
- tradeoff boundaries that do not drift into implementation repair, review findings, or
  reliability policy
- role fidelity for `R13 $performance-engineer`

## Bundle map

- `inputs/` holds the immutable evidence packet
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the expected budgets, bottlenecks, and prohibited drift
- `verifiers/` checks bundle shape and the completed performance constraint package
