# Registered downstream consumers -- usage extraction records

These records were extracted by the consumer census tool from the sixteen
registered downstream services. Consumer source code is NOT part of this
bundle and cannot be executed here; each record is the complete, authoritative
statement of how that service uses relaycfg v1.9 and what behavior it relies
on. Every listed expectation holds today on v1.9 in the listed deployment.

Record fields:

- `Deployment`: the exact file mapping (in file order), environment overlay
  mapping (already translated to dotted keys), and replica stale-key facts
  that the service runs with. Facts not listed do not occur.
- `Operations`: the exact relaycfg calls the service makes.
- `Relies on`: the recorded behavioral contract the service depends on.
  A service breaks under v2.0 exactly when at least one `Relies on` line
  stops holding for its listed operations in its listed deployment.

---

## CONS-01 `edge-router`

- Deployment: file omits `service.endpoint` in the canary profile; env overlay does not define it either.
- Operations: `client.get("service.endpoint")` -- called with no default argument.
- Relies on: an absent key returns `None`; the `None` result selects the legacy routing pool.

## CONS-02 `poller`

- Deployment: file sets `poll.interval = "250"` (bare number, no suffix).
- Operations: `client.get_duration_ms("poll.interval")`.
- Relies on: the call returns `250`, i.e. the bare value is read as 250 milliseconds.

## CONS-03 `manifest-writer`

- Deployment: file entries in file order: `zone.map = "z1"`, `region.map = "r2"`, `shard.map = "s3"`. No env overlay.
- Operations: `list(client.items())`, then writes the keys line-by-line into the deploy manifest.
- Relies on: `items()` yields entries in file order (`zone.map`, `region.map`, `shard.map`); the downstream manifest diff gate byte-compares against that order.

## CONS-04 `worker-pool`

- Deployment: file omits `workers.count` in the autoscale profile; no env overlay entry for it.
- Operations: `client.get_int("workers.count")` -- called with no default argument.
- Relies on: the call returns `None` for the absent key; `None` triggers auto-sizing.

## CONS-05 `log-shipper`

- Deployment: file sets `log.level = "debug"` and `flush.window = "500ms"`.
- Operations: `client.get("log.level", "info")`; `client.get_duration_ms("flush.window", "250ms")`; wraps both in one `except ConfigError` handler.
- Relies on: defaulted reads return the configured values (`"debug"`, `500`); config failures surface as `ConfigError`.

## CONS-06 `archiver`

- Deployment: file sets `archive.window = "2m"` and `archive.grace = "45s"`; env overlay defines only `archive.tag = "cold"` (a key the file does not define).
- Operations: `client.get_duration_ms("archive.window", "1m")`; `client.get_duration_ms("archive.grace", "30s")`; `client.get("archive.tag", "none")`.
- Relies on: suffixed durations parse to `120000` and `45000`; the overlay-only key reads as `"cold"`.

## CONS-07 `inventory-ui`

- Deployment: file entries in file order: `ui.theme = "dark"`, `asset.root = "/srv/a"`, `nav.depth = "3"`. No env overlay.
- Operations: `entries = sorted(client.items())`, then renders `entries`.
- Relies on: the sorted entry list equals the full key/value set; rendering is order-insensitive before its own sort.

## CONS-08 `billing-export`

- Deployment: file sets `billing.bucket = "b-main"` and `billing.window = "15m"`; the deployment has no environment overlay at all.
- Operations: `client.get("billing.bucket", "b-fallback")`; `client.get_duration_ms("billing.window", "10m")`.
- Relies on: defaulted reads return the configured values (`"b-main"`, `900000`).

## CONS-09 `sync-agent`

- Deployment: file sets `ledger.head = "h-77"`; during rebalance the replica marks `ledger.head` stale (routine, several times per day).
- Operations: `client.fetch("ledger.head")` inside its retry helper; the helper retries an attempt exactly when the raised error `isinstance(err, RetryableError)`, up to 3 attempts, and re-raises anything else as fatal.
- Relies on: a stale replica read is classified retryable by that `isinstance` test, so routine rebalance staleness never surfaces as a fatal error.

## CONS-10 `db-gateway`

- Deployment: file sets `db.pool = "20"`; the platform injector also sets env overlay `db.pool = "5"` (both layers define the same key).
- Operations: `client.get_int("db.pool")`.
- Relies on: the file value wins, so the pool size is `20`.

## CONS-11 `quota-auditor`

- Deployment: file sets `quota.limit = "100"`.
- Operations: calls `client.get("quota.limit")` once per audit cycle on one long-lived client (many cycles per process).
- Relies on: `client.backend_read_count()` equals the number of completed audit cycles; the metering report ships that counter as the number of backend reads.

## CONS-12 `mirror-refresher`

- Deployment: the orchestrator injects env overlay `mirror.lag.budget = "1500"` (bare number, no suffix); the file does not define the key.
- Operations: `client.get_duration_ms("mirror.lag.budget")`.
- Relies on: the call returns `1500`, i.e. a 1500 millisecond lag budget; the lag alarm compares measured lag against that budget.

## CONS-13 `replica-scanner`

- Deployment: file sets `scan.cursor = "c-9"`; the replica marks `scan.cursor` stale during compaction (routine).
- Operations: `client.fetch("scan.cursor")` inside a retry helper that retries an attempt exactly when the raised error is an instance of `StaleReadError` or `TimeoutError` (both named directly), up to 5 attempts.
- Relies on: routine stale reads are retried by that explicit two-type test.

## CONS-14 `deploy-hook`

- Deployment: file sets `release.channel = "stable"`; no stale keys.
- Operations: `client.fetch("release.channel", timeout=2.0)` -- keyword call, exactly as written.
- Relies on: that keyword call keeps working and returns `"stable"`.

## CONS-15 `metrics-relay`

- Deployment: file sets `metrics.sink = "wire"` and `metrics.batch = "40"`; env overlay defines only `trace.tag = "edge"` (no key defined in both layers).
- Operations: `client.get("metrics.sink", "null")`; `client.get_int("metrics.batch", 16)`; `client.get("trace.tag", "none")`.
- Relies on: reads return `"wire"`, `40`, and `"edge"`.

## CONS-16 `session-cache`

- Deployment: file sets `session.ttl = "600s"`.
- Operations: calls `client.get("session.ttl", "300s")` twice per request cycle.
- Relies on: both reads return `"600s"`; the record notes the service tolerates one full cycle of staleness, so a repeated read served from a local snapshot is acceptable.
