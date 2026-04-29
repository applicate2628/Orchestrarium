# S33 External-Reviewer Transport Fidelity

`S33` benchmarks `A02 $external-reviewer` on transport fidelity only. The assigned internal role in
this bundle is `$security-reviewer`, but the scored work is limited to adapter routing,
provenance, review-strategy handling, and fail-closed transport reporting. No semantic reviewer
findings, QA verdicts, or remediation advice are scored here.

## Scenario summary

An accepted upstream review phase authorizes a narrow `$security-reviewer` gate with an explicit
`adversarial` review strategy, but this scenario does not ask the candidate to perform or evaluate
that review. The adapter is routed through an explicit external provider selection in
`inputs/agents-mode.yaml`. The runtime observations show that the selected `codex` CLI is
available and that the external route completed directly through Codex CLI on the runtime default
profile. The correct result is a transport-only success report with the exact provenance header,
the preserved review strategy, and an explicit statement that no internal reviewer, QA, or
consultant fallback was used.

## Expected candidate work

Edit only `candidate/transport-execution-report.md`.

Use the immutable packet in `inputs/` to produce a transport execution report that:

- records the required provenance header with exact labels
- records the assigned review strategy and how the adapter handled it
- reports the transport-only outcome for the selected provider
- cites the canonical runtime observations instead of inventing new probes
- states that no internal reviewer, QA role, or consultant fallback was used

Do not:

- emit security findings, QA verdicts, or remediation steps
- reroute from explicit `codex` selection to `claude` or `gemini`
- discuss provider ranking or model preference beyond the transport facts in the packet
- evaluate whether the admitted semantic review would have passed

## What this bundle tests

- explicit-provider transport fidelity for `A02 $external-reviewer`
- provenance completeness and clean direct-launch reporting
- explicit review-strategy handling without semantic reviewer substitution
- rejection of hidden internal fallback as a success path

## Bundle map

- `inputs/` holds the immutable task contract, assigned reviewer packet, dispatch config, and transport facts
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth routing outcome, required provenance and strategy fields, and anti-patterns
- `verifiers/` contains a local checker for bundle shape, report schema, and completed provenance
