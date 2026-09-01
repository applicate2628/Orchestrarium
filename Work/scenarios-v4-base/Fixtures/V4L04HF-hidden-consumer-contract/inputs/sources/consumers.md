# Registered downstream consumers -- usage extraction records

These records were extracted by the consumer census tool from the
twenty-four registered downstream services. Consumer source code is NOT part
of this bundle and cannot be executed here; each record is the complete,
authoritative statement of how that service uses relaycfg v1.11 and what
behavior it relies on. Every listed expectation holds today on v1.11 in the
listed deployment.

Record fields:

- `Deployment`: the exact file mapping (in file order), environment overlay
  mapping (already translated to dotted keys), and replica stale-key facts
  that the service runs with. Facts not listed do not occur.
- `Operations`: the exact relaycfg calls the service makes.
- `Relies on`: the recorded behavioral contract the service depends on.
  A service breaks under v2.0 exactly when at least one `Relies on` line
  stops holding for its listed operations in its listed deployment.

---

## CONS-01 `edge-cache`

- Deployment: file sets `cache.ttl = "300s"` and `cache.mode = "lru"`.
- Operations: `client.get_duration_ms("cache.ttl", "60s")`; `client.get("cache.mode", "lru")`.
- Relies on: reads return `300000` and `"lru"`.

## CONS-02 `ingest-router`

- Deployment: file omits `ingest.topic` in the shadow profile; no env overlay entry for it.
- Operations: `client.get("ingest.topic")` -- called with no default argument.
- Relies on: the absent key returns `None`; `None` routes records to the bypass topic.

## CONS-03 `report-gen`

- Deployment: file entries in file order: `rep.b = "2"`, `rep.a = "1"`. No env overlay.
- Operations: `entries = sorted(client.items())`, then renders `entries`.
- Relies on: the sorted entry list equals the full key/value set; rendering is order-insensitive before its own sort.

## CONS-04 `archive-rotator`

- Deployment: file sets `rot.keep = "7"`; env overlay defines only `rot.tag = "cold"` (no key defined in both layers).
- Operations: `client.get_int("rot.keep", 5)`; `client.get("rot.tag", "none")`.
- Relies on: reads return `7` and `"cold"`.

## CONS-05 `snapshotter`

- Deployment: file sets `batch.linger = "40"` (bare number, no suffix).
- Operations: `client.get_duration_ms("batch.linger")`.
- Relies on: the call returns `40`, i.e. the bare value is read as 40 milliseconds.

## CONS-06 `deploy-hook`

- Deployment: file sets `release.channel = "beta"`; no stale keys.
- Operations: `client.fetch("release.channel", timeout=3.0)` -- keyword call, exactly as written.
- Relies on: that keyword call keeps working and returns `"beta"`.

## CONS-07 `fleet-writer`

- Deployment: file entries in file order: `fleet.zone = "fz"`, `fleet.rack = "fr"`, `fleet.node = "fn"`. No env overlay.
- Operations: `list(client.items())`, then writes the keys line-by-line into the fleet manifest.
- Relies on: `items()` yields entries in file order (`fleet.zone`, `fleet.rack`, `fleet.node`); the downstream manifest diff gate byte-compares against that order.

## CONS-08 `replica-probe`

- Deployment: file sets `probe.cursor = "p-1"`; the replica marks `probe.cursor` stale during compaction (routine).
- Operations: `client.fetch("probe.cursor")` inside a retry helper that retries an attempt exactly when the raised error is an instance of `StaleReadError` or `OSError` (both named directly), up to 5 attempts.
- Relies on: routine stale reads are retried by that explicit two-type test.

## CONS-09 `ledger-sync`

- Deployment: file sets `ledger.cursor = "L-3"`; during rebalance the replica marks `ledger.cursor` stale (routine, several times per day).
- Operations: `client.fetch("ledger.cursor")` through the service's internal `with_retries` helper; that helper retries an attempt exactly when the raised error `isinstance(err, RetryableError)`, up to 3 attempts, and re-raises anything else as fatal.
- Relies on: a stale replica read is classified retryable by that `isinstance` test, so routine rebalance staleness never surfaces as a fatal error.

## CONS-10 `session-store`

- Deployment: file sets `sess.ttl = "900s"`.
- Operations: calls `client.get("sess.ttl", "600s")` twice per request cycle.
- Relies on: both reads return `"900s"`; the record notes the service tolerates one full cycle of staleness, so a repeated read served from a local snapshot is acceptable.

## CONS-11 `pool-manager`

- Deployment: file sets `db.pool = "32"`; the platform injector also sets env overlay `db.pool = "8"` (both layers define the same key, same spelling).
- Operations: `client.get_int("db.pool")`.
- Relies on: the file value wins, so the pool size is `32`.

## CONS-12 `tag-mapper`

- Deployment: file sets `Tag.Map = "tm-1"` -- the service uses that one spelling everywhere; no other entry folds to the same key; no env overlay.
- Operations: `client.get("Tag.Map", "none")`.
- Relies on: the read returns `"tm-1"`.

## CONS-13 `meter-audit`

- Deployment: file sets `meter.scope = "org"`.
- Operations: calls `client.get("meter.scope")` once per audit cycle on one long-lived client (many cycles per process).
- Relies on: `client.backend_read_count()` equals the number of completed audit cycles; the metering report ships that counter as the number of backend reads.

## CONS-14 `flag-reader`

- Deployment: file sets `flags.beta = "false"`.
- Operations: `client.get("flags.beta", "false")`, then applies its own word parser.
- Relies on: the read returns the string `"false"`.

## CONS-15 `port-binder`

- Deployment: file sets `Server.Port = "7000"` (this exact spelling); the platform injector sets env overlay `server.port = "9000"` (lowercase spelling). Under v1.11 these are two distinct keys.
- Operations: `client.get("Server.Port")`.
- Relies on: the read returns `"7000"`, the file value under the service's own spelling.

## CONS-16 `drain-notifier`

- Deployment: file sets `drain.target = "d-9"`; the deployment guarantees the key is always present; no stale keys.
- Operations: `client.fetch("drain.target")` wrapped in one `except ConfigError` handler for replica failures.
- Relies on: the call returns `"d-9"`.

## CONS-17 `gate-keeper`

- Deployment: file entries in file order: `Feature.Gate = "on"` (team-owned stanza) followed later by `feature.gate = "off"` (legacy stanza). Under v1.11 these are two distinct keys. No env overlay.
- Operations: `client.get("Feature.Gate")`.
- Relies on: the read returns `"on"`, the team-owned entry under its exact spelling.

## CONS-18 `trace-sampler`

- Deployment: file sets `trace.window = "125ms"`.
- Operations: `client.get_duration_ms("trace.window", "100ms")`.
- Relies on: the call returns `125`.

## CONS-19 `probe-runner`

- Deployment: file omits `probe.target` while a drain is in progress (routine); no env overlay entry for it; no stale keys.
- Operations: `client.fetch("probe.target")` wrapped in a handler that catches `KeyError` and skips the probe cycle.
- Relies on: the absent key surfaces as an error the `KeyError` handler catches, so a drain never crashes the runner.

## CONS-20 `quota-viewer`

- Deployment: file sets `quota.view = "12"`; env overlay defines only `quota.edit = "3"` (no key defined in both layers).
- Operations: `client.get_int("quota.view", 0)`.
- Relies on: the read returns `12`.

## CONS-21 `mirror-lag`

- Deployment: the orchestrator injects env overlay `mirror.lag.budget = "2500"` (bare number, no suffix); the file does not define the key.
- Operations: `client.get_duration_ms("mirror.lag.budget")`.
- Relies on: the call returns `2500`, i.e. a 2500 millisecond lag budget; the lag alarm compares measured lag against that budget.

## CONS-22 `topo-render`

- Deployment: file entries in file order: `topo.c = "3"`, `topo.a = "1"`. No env overlay.
- Operations: `set(client.items())`, then renders an order-insensitive set comparison against its expected pair set.
- Relies on: the entry set equals `{("topo.a", "1"), ("topo.c", "3")}`.

## CONS-23 `backup-scheduler`

- Deployment: file sets `schedule.every = "900"` (bare number).
- Operations: `client.get_int("schedule.every", 600)` -- the service multiplies the integer itself before scheduling.
- Relies on: the read returns the integer `900`.

## CONS-24 `keyspace-lister`

- Deployment: file sets `Zone.Map = "zm-2"` -- one spelling used consistently; nothing else folds to the same key; no env overlay.
- Operations: `client.get("Zone.Map", "none")`; `len(list(client.items()))`.
- Relies on: the read returns `"zm-2"` and the listing contains exactly one entry.
