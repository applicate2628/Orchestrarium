# Scoring Anchors

Binary gate. PASS requires ALL of:

1. Bundle shape and scenario.yaml metadata match the contract exactly.
2. Required sections present; `## Gate Decision` line is `PASS`; no disallowed marker.
3. `## In Scope` covers every required in-scope group (csv; visible rows; download button/toolbar;
   filter/sort) and contains NONE of the scope-inflation terms (enforced penalty).
4. `## Out Of Scope (Parked)` contains every parked ask (extra formats; scheduled/email; dashboard/charts).
5. `## Problem Statement` mentions csv + export and contains no scope-inflation term.

## Why this separates near-peer strong product analysts

- Pulling an adjacent ask into `## In Scope` (xlsx/pdf/scheduled/email/dashboard/chart) -> enforced
  penalty -> FAIL. This is the most common near-peer failure: yielding to a tempting intake ask.
- Silently dropping an adjacent ask (not parking it) -> missing parked item -> FAIL.
- Reframing the problem as a broader reporting feature -> forbidden term in Problem Statement -> FAIL.

Holding a bounded scope against tempting adjacent asks is the discriminator, not brief length or polish.
