# Phase 03 - Execute Report

Allowed edits for this phase:

- `candidate/workspace/implementation-ledger.json`
- `candidate/workspace/src/stagegate/lease.py`
- `candidate/workspace/src/stagegate/executor.py`
- `candidate/workspace/src/stagegate/report.py`

Repair execution and reporting:

- cache restores skip staging but preserve request source and visible restore reason
- leases are released on success and failure
- failure events preserve source trace
- summary output keeps ordered source trace and per-decision source/type/artifact details

Update `implementation-ledger.json` with phase id `03-execute-report`, owner
`toolchain-engineer`, source ids `S9` through `S12`, and rejection of stale advice to keep failed
leases or omit cache restore reasons.
