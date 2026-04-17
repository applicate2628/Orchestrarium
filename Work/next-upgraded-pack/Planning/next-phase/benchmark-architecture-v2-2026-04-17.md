Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file defines the history-free benchmark architecture for the next redesign.

The old upgraded-pack architecture remains a useful execution checkpoint, but it should not define
the future benchmark taxonomy.

## Primary benchmark units

| Unit | Meaning |
|---|---|
| `Snn` | scenario bundle: the atomic benchmark asset a provider actually works on |
| `Rnn` | semantic role surface: one benchmark row for one real Orchestrator role |
| `Ann` | adapter surface: transport or runtime-contract row for non-semantic routing adapters |
| `Pnn` | pack: an admitted execution subset such as owner pack, review pack, or implementation-specialty pack |
| `Onn` | overlay: runtime or provider-specific note that should not masquerade as a role result |

## Architecture rules

| Rule | Meaning |
|---|---|
| scenarios first | every benchmark result must come from explicit scenario bundles, not from abstract line names alone |
| roles first | semantic result rows are role rows, not historical line families |
| packs are operational, not semantic | packs decide what to run together, but they are not the main result identity |
| overlays stay secondary | runtime stalls, browser-only notes, or transport caveats stay out of the primary role ranking |
| no history-derived naming dependency | the redesign does not require `M/G/W/T/L/O` continuity to be understandable |

## Scenario families

| Scenario family | Typical roles |
|---|---|
| intake and roadmap | `R01`, `R03`, `R05` |
| orchestration and recovery | `R02`, `R04` |
| repo investigation | `R06` |
| architecture and planning | `R07`, `R08`, `R09` |
| scientist and constraints | `R10`, `R11`, `R12`, `R13`, `R14` |
| backend and systems implementation | `R15`, `R19`, `R20`, `R21` |
| web UI implementation | `R16` |
| non-web UI implementation | `R17`, `R18` |
| geometry, graphics, visualization | `R22`, `R23`, `R24` |
| review and QA | `R25`, `R26`, `R27`, `R28`, `R29`, `R30`, `R31` |
| transport and adapter checks | `A01`, `A02` |

## Non-web-first principle

| Current anti-pattern | V2 rule |
|---|---|
| web worker slices dominate pack identity | web is one scenario family among many |
| static UI rows stand in for all visual work | Qt, model-view, graphics, and visualization get dedicated scenario families |
| browser/runtime parity acts like a primary quality signal | browser/runtime becomes overlay-only unless a role genuinely needs it |

## Scoring model

| Dimension | Meaning |
|---|---|
| correctness | did the role solve the benchmarked task correctly |
| role fidelity | did the response actually behave like the target role |
| scope discipline | did it stay inside the owner seam, artifact contract, and allowed surface |
| synthesis quality | did it structure and prioritize information well when the role requires judgment |
| verification cleanliness | did it verify or justify correctly without widening or noise |
| runtime cleanliness | for adapters and flaky providers, did the route complete without tool or contract pollution |

## Pack model

| Pack ID | Pack purpose | Contents |
|---|---|---|
| `P01` | owner and advisory pack | `R01..R04` |
| `P02` | factual, design, and planning pack | `R05..R09` |
| `P03` | scientist and constraint pack | `R10..R14` |
| `P04` | implementation general pack | `R15`, `R16`, `R19`, `R20`, `R21` |
| `P05` | implementation specialty pack | `R17`, `R18`, `R22`, `R23`, `R24` |
| `P06` | review and QA pack | `R25..R31` |
| `P07` | transport and runtime pack | `A01`, `A02` |

## Results model

| Surface | Meaning |
|---|---|
| role result table | the main human-facing benchmark output |
| pack result table | operational execution summary only |
| scenario result matrix | detailed per-scenario evidence |
| overlay table | runtime, transport, quota, or modality caveats |

## Boundary with current results

The current `X1/X2/X3` tables remain valid as:

- the last full execution checkpoint for the old upgraded-pack architecture

They do **not** yet answer the new design question:

- who is best for each real Orchestrator role under the right scenario family

## Next concrete design step

Derive the first scenario backlog from this architecture:

1. at least one scenario bundle per semantic role
2. at least one non-web scenario in every pack where web is not intrinsic
3. at least one ambiguity-sensitive scenario in every owner, design, and review pack
4. at least one bounded owner-seam code scenario in every implementation pack
