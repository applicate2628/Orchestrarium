# Expected Patch Shape

The correct repair for `S20` has this shape:

- update `candidate/platform-owned/observability/collector-config.yaml` so the Prometheus scrape
  path is `/metrics`, the metrics pipeline uses `resource` before `batch`, the OTLP exporter points
  at `http://otel-collector.monitoring.svc:4318`, and the collector resource attributes identify
  the `release-platform` namespace
- update `candidate/platform-owned/deploy/release-api-observability.yaml` so the deployment
  advertises `/metrics`, uses the same OTLP endpoint, and publishes the required platform resource
  attributes for `staging`

The repair should not require edits to application code, CI definitions, shared runners, provider
routing, or result snapshots.
