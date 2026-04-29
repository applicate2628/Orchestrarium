# E2 Baseline Timing And Resource Traces

## Cohort totals

| Profile | Cohort size | Cache state | Total wall time | Peak RSS | Aggregate CPU-seconds |
|---|---:|---|---:|---:|---:|
| author loop | `6` | cold run | `246s` | `1.46 GiB` | `313s` |
| author loop | `6` | warm run | `198s` | `1.34 GiB` | `272s` |
| release rehearsal | `12` | cold run | `612s` | `2.31 GiB` | `779s` |
| release rehearsal | `12` | warm run | `541s` | `2.22 GiB` | `706s` |

## Release rehearsal stage breakdown

| Stage | Mean wall time | Share of total |
|---|---:|---:|
| scan and metadata load | `41s` | `6.7%` |
| packet materialization copy | `96s` | `15.7%` |
| hash manifest build | `231s` | `37.7%` |
| archive write | `167s` | `27.3%` |
| summary index write | `77s` | `12.6%` |

## Per-scenario packet stage

- current packet-stage p95 on release rehearsal: `43s`
- current packet-stage median on release rehearsal: `35s`
- longest single scenario archive phase: `61s`

## Memory observations

- peak RSS climbs during the archive stage, after all scenario packet trees are still resident
- retained staging plus archive buffers account for roughly `1.7 GiB` of the `2.31 GiB` peak
- warm-run improvement is modest, which suggests the dominant path is not only metadata I/O
