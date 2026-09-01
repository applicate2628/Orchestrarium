# V3L01B - Product-Analyst Scope-Inflation Boundary

Target line: `L01` (product-analyst). One of the three A9 sub-scenarios in build-plan F5 that repair the
L01 lane read (analyst, product-analyst, planner).

The candidate writes a scope-bounded product brief for an accepted problem (CSV export of the currently-
visible results) and must HOLD the boundary against tempting adjacent asks in a noisy intake (extra
export formats, scheduled email export, a reporting dashboard).

## Why this separates near-peer strong product analysts (not merely hard)

The most common near-peer failure is yielding to a tempting intake ask and quietly inflating scope. The
oracle enforces a penalty: any scope-inflation term (xlsx, pdf, scheduled, email, dashboard, chart) in
the `## In Scope` or `## Problem Statement` section fails the brief, and every adjacent ask must be
explicitly parked in `## Out Of Scope (Parked)` (silently dropping them also fails). A top analyst holds
the accepted scope and parks the rest with a reason; a near-peer analyst inflates or drops. The
discriminator is scope discipline under intake pressure, not brief length or polish.

## Layout

- `inputs/` - task, accepted bounded scope, and noisy intake notes with the tempting asks.
- `candidate/product-brief.md` - the editable brief (blank start state).
- `oracle/` - contract, scoring anchors, and a passing `reference/`.
- `verifiers/check_scope_boundary.py` - deterministic, read-only, executes no candidate code.

## Terms and Abbreviations

- `scope inflation` - pulling adjacent, unfunded asks into an accepted, bounded scope.
- `park` - explicitly record an out-of-scope ask with a reason, rather than delivering or dropping it.
- `L01` - the analyst / product-analyst / planning routing line of the RF12 scorecard.
