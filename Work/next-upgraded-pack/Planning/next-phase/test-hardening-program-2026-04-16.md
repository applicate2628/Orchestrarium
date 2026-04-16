Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This file defines the hardening program for the next upgraded benchmark pack.

The rule for this phase is simple:
every active test family must be brought under one shared hardening contract.

The upgraded pack should also track hardening against one atomic `T`-series, not a mixed `M/G` naming surface.

## Shared hardening contract

| Requirement | Meaning |
|---|---|
| broken-state evidence | each test must show a real failing or degraded starting state |
| control-pass evidence | each test must have a validated correct state or control copy |
| true-owner verification | passing should require editing the real owning file or seam |
| anti-hardcode | brittle exact-path or repo-specific cheats should fail where feasible |
| anti-drift | unrelated tests, contracts, or visible surfaces should stay intact |
| distractor pressure | nearby tempting wrong files or wrong roots should exist where useful |
| bounded replayability | the test must remain runnable and explainable, not just messy for its own sake |

## Naming implication

| Rule | Meaning |
|---|---|
| hardening status should attach to `Tnn` | future status tables should not split by legacy `M` versus `G` prefixes |
| legacy aliases may remain in parentheses | use them only as migration hints |
| `W` is not a test family anymore | `W` survives only as overlay or provenance terminology |

## Hardening by family

| Family | Current state | Next upgraded requirement |
|---|---|---|
| `T01..T10` migrated legacy matrix tests | uneven; older contract and softer ownership checks | retrofit to the shared hardening contract and keep them as reusable evidence tests |
| `T11..T17` migrated early role-gap probes | useful but not all equally hardened | normalize ownership, anti-drift, and anti-hardcode checks across the set |
| `T18..T28` migrated later role-gap and trust probes | stronger than legacy tests but not perfectly uniform | backfill missing contract pieces so the whole range reads consistently |
| `O01..O05` legacy wave syntheses | historical comparison layer, not direct tests | stop treating them as direct line inputs and derive them from hardened underlying tests |
| `T29+` new upgraded probes | not built yet | design directly against the upgraded hardening contract from the start |

## Family-specific direction

| Family | Main hardening pressure to add |
|---|---|
| migrated legacy matrix tests | stronger true-owner checks and anti-drift coverage |
| migrated early role-gap probes | less toy-like structure and better anti-hardcode rejection |
| migrated later role-gap and trust probes | more explicit contract uniformity so rows are comparable |
| UI tests | non-browser by default, with wrong-file attraction and style-consistency traps |
| toolchain tests | false-root ambiguity, owner confusion, and brittle-path rejection |
| worker autonomy tests | resume pressure, stale-context rejection, and multi-step continuity checks |

## Legacy-to-upgraded family read

| Legacy read | Upgraded-pack read |
|---|---|
| `M` family | `T01..T10` |
| early `G` family | `T11..T17` |
| later `G` family | `T18..T28` |
| `W` family | `O01..O05` |

## Definition of done for hardening

| Done condition | Meaning |
|---|---|
| every active test has a hardening status | no hidden soft tests remain |
| the steady-state core pack is smaller than the full registry | routine execution stays interpretable and affordable |
| every role line is backed by multiple tests where appropriate | lines are not one-probe illusions |
| overlays are explicit | fallback or runtime notes no longer masquerade as ordinary lines |
| new fixture design follows the same contract | upgraded probes do not reintroduce benchmark drift |

## Execution-surface implication

| Surface | Role in hardening |
|---|---|
| full registry | preserve complete hardening provenance and extension space |
| steady-state core pack | regular rerun surface once tests are hardened enough |
| extended pack | confirmation and tie-break layer outside routine execution |

## Recommended order

| Step | Focus |
|---|---|
| `1` | inventory every active test and assign hardening status |
| `2` | retrofit the migrated legacy `T01..T10` range |
| `3` | normalize the migrated `T11..T28` ranges |
| `4` | redesign line synthesis around hardened tests |
| `5` | design `T29+` directly against the upgraded contract |
