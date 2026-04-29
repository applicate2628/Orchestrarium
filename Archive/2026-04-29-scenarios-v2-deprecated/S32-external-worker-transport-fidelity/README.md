# S32 External-Worker Transport Fidelity

`S32` benchmarks `A01 $external-worker` on transport fidelity only. The assigned internal role in
this bundle is `$platform-engineer`, but the scored work is limited to adapter routing,
provenance, and fail-closed transport reporting. No semantic implementation quality is scored here.

## Scenario summary

An accepted upstream phase authorizes a narrow `$platform-engineer` change, but this scenario does
not ask the candidate to perform or evaluate that phase. The adapter is routed through an explicit
external provider selection in `inputs/agents-mode.yaml`. The runtime observations show that the
selected `gemini` CLI is present on PATH, exposes non-interactive headless mode, and remains the
explicitly selected provider for this lane. The correct result is a direct-route transport report,
not an internal fallback or a reroute to a different provider.

## Expected candidate work

Edit only `candidate/transport-execution-report.md`.

Use the immutable packet in `inputs/` to produce a transport execution report that:

- records the required provenance header with exact labels
- reports a transport-only verdict for the selected provider
- cites the canonical runtime observations instead of inventing new probes
- states that no internal specialist, reviewer, or consultant fallback was used
- stays transport-only and does not implement or evaluate the admitted platform patch

Do not:

- reroute from explicit `gemini` selection to `codex` or `claude`
- substitute the assigned `$platform-engineer` role internally
- discuss provider ranking or model preference beyond the transport facts in the packet
- evaluate whether the admitted platform phase would have succeeded

## What this bundle tests

- explicit-provider transport fidelity for `A01 $external-worker`
- provenance completeness and clean direct-route reporting
- scope discipline between adapter transport work and semantic worker output
- rejection of hidden internal fallback as a success path

## Bundle map

- `inputs/` holds the immutable task contract, selected-provider config, and transport facts
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth routing outcome, provenance requirements, and anti-patterns
- `verifiers/` contains a local checker for bundle shape, report schema, and completed provenance
