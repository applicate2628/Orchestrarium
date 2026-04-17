# Budget And Bottleneck Anchors

These are the ground-truth anchors for `S13`.

## Budget anchors

- `B1` author-loop cold run must not exceed `180s` for the admitted `6`-scenario cohort
- `B2` author-loop warm run must not exceed `120s` for the admitted `6`-scenario cohort
- `B3` release rehearsal cold run must not exceed `420s` for the admitted `12`-scenario cohort
- `B4` release rehearsal packet-stage `p95` must not exceed `24s`
- `B5` release rehearsal `peak RSS` must not exceed `1.25 GiB`

## Bottleneck anchors

- `BT1` repeated recursive hash-manifest walking is the primary CPU bottleneck
- `BT2` archive write plus packet serialization is the secondary latency contributor
- `BT3` retained packet trees overlapping with archive buffers creates the main memory spike
- `BT4` the current measurement is incomplete because cold-run and warm-run variance is not
  separated by stage

## Evidence anchors

- `E2` establishes that all admitted budgets are currently missed
- `E3` establishes that hash-manifest work dominates CPU while storage queue depth stays low
- `E3` and `E5` together show that simply dropping hashing, redaction, or packet contents is not
  an admissible escape hatch
