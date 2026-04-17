Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This brief resets the benchmark redesign around the full Orchestrator role universe.

The next benchmark system should no longer be driven by:

- legacy wave history
- migration convenience
- web-heavy worker slices
- a small family of line aggregates that flatten role differences

It should instead answer one primary question:

**which provider is the best current candidate for each Orchestrator role under the right modality and pressure for that role?**

## Main objective

Build a role-complete benchmark architecture that does five things together:

1. covers the full semantic role universe rather than only a small set of merged line families
2. uses non-web-first multimodal scenario families instead of over-indexing on browser or web-style tasks
3. reveals provider-specific strengths and weaknesses instead of collapsing toward one global ordering
4. separates semantic role benchmarking from transport or runtime-adapter benchmarking
5. treats the archived and current upgraded-pack history as reference only, not as the design source

## Design reset

| Old center of gravity | New center of gravity |
|---|---|
| historical `M/G/W -> T/L/O` migration | role-complete benchmark architecture |
| small line families | one benchmark surface per role |
| worker-heavy regular pack | balanced modality mix across owner, research, design, scientist, implementer, reviewer, and archivist roles |
| web and static-UI pressure as dominant differentiators | web as one modality among several |
| binary pass/fail with a few caveats | richer role-fidelity scoring with correctness, scope discipline, synthesis quality, and transport cleanliness |

## Non-negotiable redesign rules

| Rule | Meaning |
|---|---|
| role-complete | every semantic role in the current `AGENTS.md` role index must have a benchmark surface |
| non-web-first | web scenarios are allowed, but they must not dominate the benchmark system |
| modality-fit | each role gets scenarios that match its real output type: memo, plan, code patch, review findings, orchestration packet, archive hygiene, and so on |
| provider-sensitive | the pack should create room for Claude, Codex, Gemini, and future providers to win different roles for real reasons |
| no-history-dependence | historical benchmark assets may be reused as raw ingredients, but the new architecture must not inherit their row model or naming as its primary structure |
| adapters-not-abilities | transport adapters such as `$external-worker` and `$external-reviewer` are benchmarked separately from semantic role ability |

## In scope

| Scope | Meaning |
|---|---|
| role inventory reset | define the benchmarked role universe directly from the current `AGENTS.md` |
| new taxonomy | replace the history-derived line model with a role-first model |
| scenario-family design | define non-web, web, code, review, orchestration, and archive scenario families |
| scoring redesign | define per-role scoring dimensions beyond raw pass/fail |
| pack redesign | define core, specialty, and transport packs without inheriting the old worker-heavy balance |
| results redesign | publish results by role, not only by historical or execution surface |

## Out of scope

| Out of scope | Reason |
|---|---|
| reinterpreting current `X1/X2/X3` results as final role-complete answers | the current results belong to the old upgraded-pack architecture |
| preserving the old `10` line families as the future main surface | that model is now too coarse for the stated goal |
| browser-first parity work | browser/runtime remains optional supplemental evidence, not the benchmark center |
| archive mutation | archive stays frozen and historical |

## Required outputs

| Output | Destination |
|---|---|
| redesign brief | `Planning/next-phase/phase-brief-role-complete-redesign-2026-04-17.md` |
| role coverage matrix | `Planning/next-phase/role-coverage-matrix-2026-04-17.md` |
| benchmark architecture v2 | `Planning/next-phase/benchmark-architecture-v2-2026-04-17.md` |
| updated planning README | `Planning/next-phase/README.md` |
| updated live status | `Checkpoints/status-2026-04-16.md` |

## Success criteria

| Criterion | Meaning |
|---|---|
| every semantic role has a named benchmark surface | no meaningful role is left implicit or absorbed beyond recognition |
| non-web roles have first-class scenarios | backend, toolchain, data, Qt, model-view, geometry, graphics, visualization, planning, review, and archive roles are not treated as side notes |
| results can differ by role | the system is no longer optimized to collapse toward one provider order everywhere |
| adapters are measured honestly | runtime transport success and semantic role quality are not confused with one another |
| archive is demoted to reference | old packs remain useful evidence, but no longer dictate the future model |

## Next concrete action

Translate the role universe into:

1. a role coverage matrix
2. a clean benchmark taxonomy
3. scenario-family packs that can later produce new fixtures and new result tables
