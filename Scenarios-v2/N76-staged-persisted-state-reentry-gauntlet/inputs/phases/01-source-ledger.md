# Phase 01: Source Ledger

Create or update only:

- `candidate/source-ledger.json`
- optionally `candidate/reentry-state.json`

Read `inputs/task.md` and record source decisions before implementation.

Required source decisions:

- `INC-STATE-219`: accept as the live incident. It says schema-v2 replay must preserve
  `dedupe_key`, `checkpoint_id`, source immutability, and persist/load envelope behavior.
- `ADR-42`: accept as architecture direction. It says v1 compatibility remains required, but
  canonical state snapshots must be schema-v2.
- `runtime-trace`: accept as runtime evidence. It shows duplicate event replay currently double
  applies `dedupe_key` and rollback returns the final state instead of a historical checkpoint.
- `visible-test`: accept as insufficient guard. It covers only v1 credit/debit balance and must be
  extended.
- `stale-v1-only-note`: reject. It says to keep only v1 events and skip schema-v2 envelope work.
- `shortcut-no-rollback`: reject. It says rollback can be documented without runtime behavior.

The source ledger must use explicit `accepted` / `rejected` decisions, owner file, and return cue for
each source. Do not edit implementation files in this phase.
