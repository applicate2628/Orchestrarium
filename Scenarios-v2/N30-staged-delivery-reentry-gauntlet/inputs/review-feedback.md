# Review Feedback Packet

Handle the real review items and reject the decoys in `candidate/review-response.json`.

| ID | Decision | Owner | Requirement |
|---|---|---|---|
| `R1-stable-idempotency` | accept | `candidate/workspace/src/releaseflow/executor.py` | action keys must not include retry attempt or resume token |
| `R2-report-source` | accept | `candidate/workspace/src/releaseflow/report.py` | final report must use ledger/audit state |
| `R3-tests-cover-stale-profile` | accept | `candidate/workspace/tests/test_releaseflow.py` | tests must prove `activeProfile` beats stale `legacyProfile` |
| `R4-ui-badge-decoy` | reject | `candidate/workspace/ui/status_badges.py` | UI labels do not own runtime state |
| `R5-legacy-helper-decoy` | reject | `candidate/workspace/legacy/report_old.py` | archived helper must stay untouched |
