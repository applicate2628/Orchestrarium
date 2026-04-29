# Owner Map

## Platform-owned seam

These two config files are the only editable surfaces in this bundle:

- `candidate/platform-owned/observability/collector-config.yaml`
- `candidate/platform-owned/deploy/release-api-observability.yaml`

The direct validation route in `candidate/platform-owned/scripts/` is read-only support material,
not part of the patch surface.

## Read-only surfaces

- `candidate/platform-owned/fixtures/**` is immutable contract data for the validator
- `candidate/backend-code/**` is application instrumentation already owned elsewhere
- `candidate/toolchain-owned/**` is CI and packaging ownership, not platform observability repair
- `candidate/shared-runners/**` is shared execution wiring outside this scenario
- `candidate/provider-routing/**` is provider selection evidence and stays out of scope
- `candidate/results-surfaces/**` is stale results output and must not become the repair target

Editing any read-only surface is scope drift even if the local validator starts to pass.
