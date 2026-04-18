# Inputs

This directory is the immutable packet for the `N02` UX-design scenario. It focuses on
interaction-state flow, interruption handling, and return-loop reasoning, not implementation or
review output.

## Included materials

- `task.md` defines the benchmark task and required UX-brief output
- `accepted-brief.md` states the admitted problem, users, and protected surface split
- `current-state-handshake-audit.md` describes the current desktop/web states and transitions
- `interruption-and-return-loop-friction.md` records the main interruption failures and lost-place
  scenarios
- `boundary-rules.md` clarifies what belongs in UX design versus implementation, architecture, or
  later review output

The packet is intentionally state-flow-specific. A generic information-architecture memo, code
patch plan, or review findings report will miss the required interruption and resumability work.
