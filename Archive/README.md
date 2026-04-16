Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This directory stores immutable archived benchmark snapshots.

Each snapshot is a dated package that preserves:

- admitted result tables
- checkpoint and method context
- supporting evidence
- benchmark-side tooling referenced by the archive

## Current snapshots

| Snapshot | Role |
|---|---|
| `2026-04-16-first-baseline/` | first archived baseline package extracted from the benchmark line |

## Archive rule

| Rule | Meaning |
|---|---|
| snapshots are frozen | new benchmark packs should not rewrite old snapshots |
| add new snapshots, do not overwrite old ones | if a later pack becomes admitted, archive it as a new dated snapshot |
| preserve traceability | each snapshot should stay internally navigable on its own |
