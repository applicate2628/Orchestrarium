# Failing Validation Snapshot

Expected start-state output from `python scripts/validate_observability_patch.py` in
`candidate/platform-owned/`:

```text
S20 validation FAIL
collector-exporter-endpoint
collector-metrics-path
collector-metrics-processors
collector-resource-attributes
deployment-otlp-endpoint
deployment-prometheus-path
deployment-resource-attributes
```

The author-side start-state verifier checks for exactly these failure ids and no others.
