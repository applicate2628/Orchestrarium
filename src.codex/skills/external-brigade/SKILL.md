---
name: external-brigade
description: Launch and aggregate a bounded brigade of parallel external helpers when multiple independent external lanes or slices should run together.
---

# External Brigade

Use this utility when a bounded set of external helper runs should launch in parallel instead of being described piecemeal inside ad hoc lead notes.

## When to use

- More than one independent external helper lane is ready at the same time.
- The task needs a mix of advisory, worker-side, or review-side external artifacts in one bounded batch.
- The same external provider may need to be reused across multiple disjoint slices or admitted artifacts.
- Internal native slot limits would otherwise slow clearly eligible external work.

## Do not use

- For owner lanes such as `$lead` or `$product-manager`.
- For overlapping write surfaces.
- For one vague request like "ask externals to help with everything."
- When one ordinary external helper invocation is enough.

## Brigade item contract

Each brigade item must name:

- execution role: `consultant`, `external-worker`, or `external-reviewer`
- assigned / replaced internal role, or `none` for pure advisory
- lane classification
- goal and expected artifact
- approved inputs
- allowed tools
- scope and out of scope
- allowed change surface
- must-not-break surfaces when code or docs may change
- provider selection: explicit provider or `auto`
- whether the item is required or explicitly optional

One brigade item equals one helper instance, one admitted artifact, and one gate.

## Routing rules

1. Read and normalize `.agents/.agents-mode.yaml` before trusting any flags.
2. Honor the current external routing fields, including:
   - `consultantMode` (allowed: `external | internal | disabled`; default: `disabled`)
   - `externalClaudeApiMode` (allowed when Claude Code is the resolved provider for this run: `disabled | auto | force`; default: `auto`)
   - `externalProvider`
   - `externalPriorityProfile`
   - `externalPriorityProfiles`
   - `externalOpinionCounts`
   - `externalCodexWorkdirMode`
   - `externalClaudeWorkdirMode`
   - `externalGeminiWorkdirMode`
   - `externalModelMode`
   - `externalGeminiFallbackMode`
   - `externalClaudeProfile`
3. Reject unsupported owner routes before provider resolution.
4. Keep `externalOpinionCounts` scoped to same-lane distinct-opinion requirements. It does not cap how many same-provider brigade items may run in parallel across different disjoint lanes or slices.
5. Allow repeated same-provider fan-out when each brigade item owns a different admitted artifact or disjoint slice and the provider runtime supports concurrent non-interactive execution.
6. If a brigade item itself requires `2+` same-lane opinions, satisfy that distinct-provider requirement first or fail that item closed.
7. Do not silently downgrade external items to internal execution inside the brigade.

## Return exactly one artifact

Return one brigade report with:

1. Brigade summary
2. Launch table
3. Aggregated artifact / findings pointers
4. Open blockers or shortfalls
5. Gate: `PASS` | `REVISE` | `BLOCKED:dependency`

The launch table must keep these columns explicit:

| Item | Execution role | Assigned / replaced internal role | Requested provider | Resolved provider | Scope | Result |
| --- | --- | --- | --- | --- | --- | --- |
| `<item>` | `<role>` | `<role or none>` | `<internal | codex | claude | gemini>` | `<provider or none>` | `<one-line scope>` | `<PASS | REVISE | BLOCKED>` |

## Gate rules

- `PASS` only when every required brigade item produced its required artifact.
- `REVISE` when at least one required item returned `REVISE` and no required item is blocked.
- `BLOCKED:dependency` when a required item cannot run, when a same-lane distinct-opinion count cannot be satisfied, or when the requested brigade is structurally invalid.
- Optional items may be skipped only when the approved brief marks them optional explicitly.

## Non-goals

- Not a new specialist role.
- Not a replacement for `$lead`.
- Not a way to hide overlapping write scopes.
- Not a way to collapse multiple unrelated artifacts into one vague helper request.
