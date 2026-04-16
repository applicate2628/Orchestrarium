# W5 X2 Fallback Reasoning Synthesis

Date: 2026-04-14
Owner: `$lead`
Status: `PASS`

## Scope

Completed `W5` for the only fallback target that cleared the `W4` gate:

- `X2` Codex fallback (`gpt-5.3-codex-spark`)

Covered tests:

- `M03` ADR-style architecture memo
- `M04` phased delivery plan
- `M06` security or threat memo
- `M07` performance memo
- `M10` resume and stale-context rejection

`X6` was not reopened for `W5` in this historical wave; that historical gate now needs to be read alongside the later Gemini 3 HIGH reruns rather than as the current exact-target stop rule.

## Historical alignment note

This file remains a historical 2026-04-14 fallback-wave snapshot. Current routing should defer to `matrices/model-matrix-checkpoint-2026-04-15.md` and `matrices/model-only-recommendation-package-2026-04-15.md`, which integrate the later Gemini repin and the stricter current `G08` result.

## Aggregate picture

| Target | Overall picture | Current bounded verdict |
|---|---|---|
| `X2` | passed the full reasoning-expansion batch without invalidity; strongest on planning/performance discipline, slightly lighter than `X1` and `X3` on the highest-depth advisory wording, and still noisy at the runtime envelope level | admitted beyond mechanical lanes as a broader Codex overflow fallback; keep `X1` as the preferred Codex path |

## Test-by-test signal

| Test | Current verdict | Key reason |
|---|---|---|
| `M03` | strong | preserved the two-layer provider-vs-path rule cleanly and stayed fully inside the admitted provider enum |
| `M04` | strong | produced a complete phased plan with the correct blocked-`X4` fixture assumption and tighter scope coverage than the earlier `X1` row |
| `M06` | usable-to-strong | threat-aware, concrete, and scoped correctly, though still a little lighter than the strongest Claude/Codex top-path memos |
| `M07` | strong | gave measurable budgets, repeat rules, and instability handling without drift |
| `M10` | usable-to-strong | resumed correctly and rejected stale context explicitly, but was less sharp than `X1` on next-step sequencing |

## Stage-2 gate decision

| Gate | Outcome |
|---|---|
| any invalidity in `M03`, `M04`, `M06`, `M07`, `M10` | no |
| repeated reasoning-collapse signal | no |
| broader reasoning expansion threshold | cleared from the accepted qualitative rubric read |
| final `W5` decision for `X2` | `GO` for broader overflow use, with a runtime-noise caveat |

## Pairwise synthesis

### `X1↔X2`

| Field | Verdict |
|---|---|
| architecture and planning work | `X1` stays slightly cleaner overall, but `X2` is now clearly admissible |
| security and performance memos | `X1` still leads, though the gap is moderate rather than disqualifying |
| resume discipline | `X1` remains sharper |
| overall pairwise verdict | `near-substitute` |
| routing implication | inside Codex, keep `X1` first and admit `X2` as a broader overflow fallback for advisory, planning, review, implementation, and debugging lanes |

### `X3↔X2`

| Field | Verdict |
|---|---|
| reasoning depth | `X3` still leads on higher-order advisory polish |
| correctness and scope control | both are admissible |
| overall pairwise verdict | `bounded substitute only` for the highest-depth slot-1 advisory use; usable as overflow |
| routing implication | do not change provider order on advisory lanes; `claude` stays slot 1 and `codex` stays slot 2 |

### `X2↔X5`

| Field | Verdict |
|---|---|
| reasoning breadth | `X2` now leads |
| cleanliness | `X5` remains cleaner operationally |
| overall pairwise verdict | `near-substitute`, favoring `X2` |
| routing implication | current advisory and planning lane guidance should continue to keep `codex` ahead of `gemini` when the fallback shape matters |

## Lane-priority implications

| Lane or lane set | Preferred provider order | Codex-local note | Confidence |
|---|---|---|---|
| `advisory.design-adr` | `[claude, codex, gemini]` | inside Codex prefer `X1`; `X2` is now admitted overflow rather than mechanical-only | medium |
| `planner.delivery-phasing` | `[claude, codex, gemini]` | `X2` is now admitted overflow for planning work | medium |
| `advisory.security-transport` | `[claude, codex, gemini]` | `X2` is admitted overflow, but still below `X1` and `X3` | medium |
| `advisory.performance-benchmarking` | `[claude, codex, gemini]` | `X2` is admitted overflow; keep runtime-noise caveat explicit | medium |
| `lead.resume-orchestration` | `[claude, codex, gemini]` | `X2` is admissible, but `X1` remains the sharper Codex-side resume path | medium |
| `review.pre-pr` | `[claude, codex, gemini]` | unchanged from `W4`: `X2` remains admitted fallback and `X6` remains excluded | high |
| `worker.default-implementation` | `[codex, claude, gemini]` | unchanged provider order; `X2` remains an admitted Codex overflow fallback | high |
| `worker.root-cause-debugging` | `[codex, claude, gemini]` | unchanged provider order; `X2` remains an admitted Codex overflow fallback | high |

## Matrix effect

| Question | Current answer |
|---|---|
| does `W5` change provider order on advisory lanes | no |
| is `X2` still mechanical-only | no |
| should `X2` now be considered beyond mechanical lanes | yes, as a broader overflow fallback with runtime-noise caveat |
| should `X6` be reopened because `X2` passed `W5` from this historical wave alone | no |

## Current recommendation

| Question | Current answer |
|---|---|
| strongest Codex path | `X1` |
| strongest Codex fallback | `X2` |
| can `X2` handle architecture, planning, security, performance, and resume tasks | yes, as overflow rather than primary slot-1 guidance |
| does `X2` displace `X1` or `X3` | no |
| does `X2` materially strengthen Codex provider resilience under fallback | yes |

## Next step

Update the current model matrix checkpoint and task memory so the model-only track reflects that `X2` is no longer mechanical-only, while keeping the MCP track deferred.
