# E3 Bottleneck Probe Notes

## Sampling summary

Release rehearsal was sampled at `100 ms` intervals for three warm runs.

- `BT1 candidate`: recursive hash-manifest walking plus SHA-256 accounted for `44%` of sampled CPU
  time
- `BT2 candidate`: archive compression plus JSON packet serialization accounted for `29%`
- `BT3 candidate`: repeated `scenario.yaml` parse and pack metadata normalization accounted for
  `11%`
- remaining sampled time was split across file copy setup, temporary-path bookkeeping, and summary
  write

## Resource read

- CPU utilization stayed above `88%` on one to two cores during hash-manifest build
- storage queue depth stayed below `1.2`, even during the slowest runs
- memory pressure rose late in the run because packet trees and archive buffers overlapped in
  lifetime
- no network traffic or browser activity is present in the admitted flow

## Measurement blind spots

- the traces do not isolate bytes read and bytes written per stage
- cold-run and warm-run stage timings were captured, but variance was not reported separately by
  stage
- the stretch `24`-scenario observation recorded only total wall time, not a full stage breakdown
