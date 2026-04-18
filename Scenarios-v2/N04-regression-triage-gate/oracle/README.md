# Oracle

The oracle material defines the ground-truth triage outcome for `N04`.

## Triage truth

The packet should not pass the regression gate. The correct triage report returns `REVISE` because
dry-run writes a run marker, the failure-only footer counts the wrong set, and the digest key now
changes on minute boundaries for identical `ops-summary` reruns.

## Included oracle files

- `regression-triage-contract.json` provides machine-readable bundle and report anchors
- `expected-regressions.md` lists the required likely regressions and their intended priority
- `severity-anchors.md` defines the triage severity scale
- `false-positive-traps.md` documents tempting but incorrect escalations
- `scoring-anchors.md` maps strong and weak `N04` runs
- `report-boundary.md` keeps the result triage-only
