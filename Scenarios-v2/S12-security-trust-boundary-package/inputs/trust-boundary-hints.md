# Evidence E2 - Trust Boundary Hints

The following boundaries are expected to matter. The candidate still needs to describe why each
boundary exists and what must be controlled at that edge.

## Boundary candidates

- `TB1` scenario bundle content vs runner-owned workspace and staging area
- `TB2` runner-orchestrator vs credential broker
- `TB3` runner/provider launcher vs the external provider transport
- `TB4` raw evidence vault vs analyst export package
- `TB5` human operator approvals vs service-account automation

## Notes

- `scenario.yaml` and attachment manifests are candidate-controlled inputs from the runner's point
  of view
- the provider CLI is an allowed integration point but it is still outside the trusted computing
  boundary of the local runner
- provider stdout, stderr, and returned attachments must be treated as untrusted until validated
- the analyst export package is intentionally broader-access than the raw evidence vault
