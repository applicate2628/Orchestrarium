# Observability Contract

The admitted release telemetry contract for this bundle is:

- the collector's Prometheus scrape path is `/metrics`
- the deployment advertises the same scrape path through `prometheus.io/path`
- the collector metrics pipeline uses processors in this order:
  1. `resource`
  2. `batch`
- both config files point OTLP traffic at `http://otel-collector.monitoring.svc:4318`
- the required resource attributes are:
  - `service.name=release-api`
  - `service.namespace=release-platform`
  - `deployment.environment=staging`

No backend code changes are needed. The app already exposes `/metrics`; the bug is in platform
configuration only.
