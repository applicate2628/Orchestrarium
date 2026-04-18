# N05 Secret Exposure Review

`N05` benchmarks `R27 $security-reviewer` on a bounded secret-exposure gate. The candidate is
reviewing a read-only export-preview change and must produce a findings-only report. The candidate
does not patch code, rewrite the data-handling design, or turn the task into a worker bundle.

## Scenario summary

An export-preview surface reached the security review lane after implementation. The feature team
claims the panel is "staff only", but the gate still has to verify that export tokens and customer
data do not leak through URLs, telemetry, or visible UI traces before merge.

## Expected candidate work

Edit only `candidate/review-report.md`.

Use the immutable materials in `inputs/` together with the read-only review target in
`candidate/review-target/`. The correct outcome is a findings-first security report that:

- identifies the blocking secret exposure in the export URL and telemetry path
- identifies visible customer-data exposure without drifting into patch design
- cites bundle-local file paths and observations as evidence
- ends with a gate decision of `REVISE`

## What this bundle tests

- findings-only security review on a bounded additive surface
- severity discipline for secret and data-exposure risks
- false-positive control when the target contains some harmless presentation details
- review-only separation for a `P06` security gate

## Bundle map

- `inputs/` holds the task contract, accepted security claims, observations, and review boundary
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, severity anchors, false-positive traps, and scoring
  read
- `verifiers/` contains a local checker for the bundle contract and an optional completed report
