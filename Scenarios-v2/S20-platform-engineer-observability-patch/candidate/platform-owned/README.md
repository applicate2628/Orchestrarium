# Platform-Owned Workspace

This workspace contains the bundle-local observability assets for `S20`.

## Contents

- `observability/collector-config.yaml` is the collector configuration
- `deploy/release-api-observability.yaml` is the deployment-side telemetry wiring
- `fixtures/observability-contract.json` is the immutable expected contract
- `scripts/validate_observability_patch.py` is the direct validation route

## Validation

Run the validator from this directory:

```bash
python scripts/validate_observability_patch.py
```

The editable config files are JSON-shaped YAML so the validator can stay dependency-free and
deterministic.
