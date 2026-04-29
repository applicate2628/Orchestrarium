# Task

Repair the bundle-local observability configuration for the staged `release-api` deployment.

## Goal

Bring the collector and deployment config back into the admitted platform contract so the direct
validation route passes without edits outside the platform-owned workspace.

## Required end state

- metrics are scraped from `/metrics`
- the collector metrics pipeline applies `resource` before `batch`
- the collector exporter and deployment OTLP endpoint both use
  `http://otel-collector.monitoring.svc:4318`
- platform resource attributes identify the service as `release-api` in the
  `release-platform` namespace and `staging` environment

## Direct validation route

Run this command from `candidate/platform-owned/` after the patch:

```bash
python scripts/validate_observability_patch.py
```

The config files are JSON-shaped YAML on purpose so the local validator can read them without extra
dependencies.
