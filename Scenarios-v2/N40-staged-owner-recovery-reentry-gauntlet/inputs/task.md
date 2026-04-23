# Task

You are acting as `$lead` on a staged owner-recovery packet.

## Goal

Recover the current benchmark lane state without relying on stale winner tables, decide the next
run order, and leave a durable resume point.

## Required behavior

- Bind the decision to current sources `S1..S10`.
- Reject stale sources `ST1..ST7`.
- Keep old full-v2 denominator, diagnostic overlays, staged separators, and queued tasks separate.
- Preserve lane-specific routing instead of declaring a global winner.
- Classify quota, route failures, wrapper timeouts, and missing summaries as runtime caveats, not
  model semantic failures.
- Keep X4 `NOT-RUN`.
- Run top-pair rows first for queued N38/N39/N40, then calibrate X2 and only run X5/X6 when route
  health is useful.
- Make `N38,N39,N40` queued tasks, not admitted result evidence.
- Close with exact changed paths, validation commands, and resume point.
