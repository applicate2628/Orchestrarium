---
name: agents-external-brigade
description: Launch a bounded parallel set of external helpers for independent admitted lanes or disjoint slices.
disable-model-invocation: true
---
# External Brigade

Launch a bounded parallel set of external helpers for independent admitted lanes or disjoint slices.

## Steps

1. **Read the current contract.**
   - Read `.claude/CLAUDE.md`.
   - Read `.claude/agents/contracts/external-dispatch.md`.
   - If `.claude/.agents-mode.yaml` exists, read and normalize it before trusting any routing flags.

2. **Build the brigade table.**
   - Identify each brigade item separately.
   - Each item must specify:
     - execution role: `consultant`, `external-worker`, or `external-reviewer`
     - assigned / replaced internal role, or `none` for advisory-only work
     - expected artifact
     - scope and out of scope
     - allowed change surface
     - requested provider: explicit or `auto`
     - whether the item is required or optional

3. **Reject invalid brigade shapes.**
   - Fail fast on owner lanes such as `$lead` or `$product-manager`.
   - Fail fast on overlapping write surfaces.
   - Do not turn one vague request into an implicit brigade.

4. **Route the brigade honestly.**
   - Use `.claude/.agents-mode.yaml` for `externalProvider`, `externalPriorityProfile`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalClaudeSecretMode`, and `externalClaudeApiMode`.
   - Keep `externalOpinionCounts` scoped to same-lane distinct-opinion requirements. Do not misuse it as a concurrency cap.
   - Allow repeated same-provider helper instances when different brigade items own different admitted artifacts or disjoint slices and the runtime supports concurrent non-interactive execution.
   - If one brigade item requires multiple same-lane opinions, satisfy that distinct-provider requirement fail closed before declaring that item complete.

5. **Launch only the eligible items.**
   - Run independent external helpers in parallel when their scopes are honestly disjoint.
   - Do not silently downgrade a failed external item to an internal specialist inside this skill.

6. **Return one brigade report.**
   - Include:
     - brigade summary
     - launch table
     - aggregated artifact / findings pointers
     - open blockers or shortfalls
     - final gate: `PASS`, `REVISE`, or `BLOCKED:dependency`

## Required launch table

| Item | Execution role | Assigned / replaced internal role | Requested provider | Resolved provider | Scope | Result |
| --- | --- | --- | --- | --- | --- | --- |
| `<item>` | `<role>` | `<role or none>` | `<internal | codex | claude | gemini>` | `<provider or none>` | `<one-line scope>` | `<PASS | REVISE | BLOCKED>` |

## Rules

- This is an operator surface, not a new specialist role.
- Keep one brigade item equal to one helper instance, one admitted artifact, and one gate.
- Optional brigade items must be explicitly marked optional in the approved brief.
- If a required brigade item cannot run or cannot satisfy its distinct-opinion requirement, the brigade stays blocked.
