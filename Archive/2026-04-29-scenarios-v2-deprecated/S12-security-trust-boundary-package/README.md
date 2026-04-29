# S12 Security Trust-Boundary Package

`S12` benchmarks `R12 $security-engineer` on a non-web, evidence-heavy trust-boundary analysis.
The candidate is asked to produce one security constraint package for a proposed
`relay-and-export` mode in the benchmark runner. The package must translate the supplied evidence
into explicit trust boundaries, required controls, must-fix constraints, abuse cases, verification
expectations, and falsifiable security claims.

## Scenario summary

The proposed runner flow is entirely local and CLI-driven:

1. an operator launches a batch run from a workstation
2. the runner reads scenario materials from the repo
3. the runner asks a local credential broker for short-lived provider and vault tokens
4. the runner invokes an external provider CLI with staged inputs
5. raw artifacts are written to a restricted evidence vault
6. a redacted analyst package is emitted for broader internal review

The immutable evidence shows that the current design draft crosses trust boundaries incorrectly:
secrets are leaking into debug capture, bundle-controlled paths are not fully confined, provider
output is being treated as if it were trusted, and the raw evidence boundary is not separated
cleanly from the analyst export boundary.

All security materials in this bundle are synthetic or redacted. No real credentials, live tokens,
or runnable provider wrappers are included.

## Expected candidate work

Edit only `candidate/security-constraint-package.md`.

Use the evidence packet in `inputs/` to produce a security-engineer artifact, not an implementation
patch and not a findings-only review. A strong answer keeps the work in the constraint lane:

- define the trust boundaries the design must respect
- classify sensitive assets and abuse cases
- require concrete controls tied back to the evidence
- state must-fix items and implementation constraints
- define verification expectations for later planning and review
- include a numbered claims section and a final gate decision

## What this bundle tests

- trust-boundary precision instead of generic security advice
- control selection grounded in concrete evidence
- discipline about untrusted outputs, secret handling, and publication boundaries
- role fidelity for `R12 $security-engineer`

## Bundle map

- `inputs/` holds the immutable evidence packet
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the expected trust boundaries, controls, and anti-patterns
- `verifiers/` checks bundle shape and the completed security package
