# Candidate Root

This is the mutable run root copied for each scored execution.

The only editable surface is the pair of platform-owned config files under `platform-owned/`. The
start state is intentionally wrong because the collector and deployment still use legacy scrape
paths, OTLP endpoints, and platform resource attributes.

## Editable files

- `platform-owned/observability/collector-config.yaml`
- `platform-owned/deploy/release-api-observability.yaml`

## Read-only context inside the candidate root

- `platform-owned/README.md`
- `platform-owned/fixtures/`
- `platform-owned/scripts/`
- `backend-code/`
- `toolchain-owned/`
- `shared-runners/`
- `provider-routing/`
- `results-surfaces/`

The intended repair path is to keep the change inside the bundle-local platform seam and validate
it with the direct local route only.
