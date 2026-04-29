# E4 Budget Envelope

These are the operator-approved targets for the next accepted design iteration.

## Required budgets

- `B1` author-loop cold run: at or below `180s` for the `6`-scenario cohort
- `B2` author-loop warm run: at or below `120s` for the `6`-scenario cohort
- `B3` release rehearsal cold run: at or below `420s` for the `12`-scenario cohort
- `B4` release rehearsal packet-stage p95: at or below `24s`
- `B5` peak RSS: at or below `1.25 GiB` on the release worker

## Why these budgets matter

- author iteration becomes disruptive above a three-minute cold run and a two-minute warm run
- release rehearsal must stay inside a seven-minute CI slot without borrowing time from later gates
- the release worker cannot reserve more memory without displacing other local verification jobs

## Stretch note

The `24`-scenario stretch case is informative only. It may guide the bottleneck model, but it is
not an admitted pass or fail budget for this package.
