# Phase 01 - Source Plan

Allowed edits for this phase:

- `candidate/workspace/implementation-ledger.json`
- `candidate/workspace/src/stagegate/config.py`
- `candidate/workspace/src/stagegate/paths.py`

Repair configuration and path resolution:

- active channel settings win over `legacyChannel`
- `STAGEGATE_ROOT` overrides only when it is an absolute path
- invalid relative env roots fall back to the active channel staging root
- all staging roots use `/` separators and no trailing slash

Update `implementation-ledger.json` with phase id `01-source-plan`, owner `toolchain-engineer`,
source ids `S1` through `S4`, and rejection of stale advice that legacy channel or relative roots
should win.
