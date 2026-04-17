# Subagent Contracts

Handoff templates and response format for lead-to-specialist delegation.

## Execution mechanism

Every specialist invocation MUST use the **Agent tool** with the matching `subagent_type` parameter, except provider-backed external adapter routes. `$external-worker` and `$external-reviewer` are direct external launch routes, not internal specialist-agent hosts. The handoff template below becomes the agent's `prompt` for ordinary specialists. The orchestrator (main conversation or lead) MUST NOT role-play specialists inline — each role runs in an isolated agent context.

## External dispatch contract

Use this contract when `subagent_type` is `external-worker` or `external-reviewer`.

- These roles are routing adapters, not new business professions.
- The `Assigned role` field names the internal role being replaced for provenance.
- Read and normalize `.claude/.agents-mode.yaml` first. Honor `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, `externalPriorityProfile`, `externalPriorityProfiles`, `externalOpinionCounts`, `externalModelMode`, `externalGeminiFallbackMode`, and `externalClaudeApiMode` when they are present. On the Claude line, do not write `externalClaudeProfile` into the canonical `.agents-mode.yaml` file; it remains Codex-line only.
- If local `.claude/.agents-mode.yaml` is missing, read local legacy `.claude/.agents-mode` as compatibility input only; if both local files are missing, fall back to global `~/.claude/.agents-mode.yaml` and then global legacy `~/.claude/.agents-mode`. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope and do not recreate any legacy file.
- Resolve external routing in this order: `role eligibility -> provider selection -> CLI availability`.
- There is no generic external adapter for owner roles such as `$product-manager` or `$lead`. If a request lands in one of those lanes, fail fast with an unsupported-route explanation instead of probing providers.
- Do not silently fall back to an internal specialist if the external CLI is unavailable; the adapter is disabled and the orchestrator may reroute.
- Do not satisfy `$external-worker` or `$external-reviewer` by spawning an internal agent/helper/subagent host that merely relays to another CLI. If the current runtime cannot launch the selected external provider directly, the route is unavailable.
- `external-worker` covers the full worker-side lane.
- `external-reviewer` covers review and QA-side work.
- `externalProvider: auto` resolves by the active named priority profile instead of a host-line default; explicit `codex`, `claude`, or `gemini` may be selected when the route is eligible. If a repository wants Gemini-first routing for image/icon/decorative visual lanes, express that through an explicit provider override or a repo-local custom profile.
- Independent external adapters may run in parallel when their scopes are disjoint and provider runtimes support concurrent non-interactive execution. If native internal slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.
- Same-provider reuse is allowed for independent external fan-out. Do not impose a one-instance-per-provider cap when multiple admitted artifacts or disjoint slices need the same helper/provider combination.
- `externalOpinionCounts` still governs distinct-provider opinion requirements for one lane; it does not limit brigade-style parallel launches across different independent lanes or slices.
- When the routing decision is "launch a bounded set of external helpers together", prefer `/agents-external-brigade` so the brigade has one explicit plan, one ownership table, and one aggregated result surface.

For external adapters, include the provenance header from `external-dispatch.md` in the returned artifact.

## Handoff template

```text
Role:
Goal:
Approved inputs:
- <accepted artifact or fact>
Allowed tools:
- <allowed tool>
Scope:
- <allowed area>
Out of scope:
- <forbidden area>
Allowed change surface:
- <approved files, modules, or seams>
Must-not-break surfaces:
- <nearby but unrelated areas that need isolation or smoke coverage>
Constraints:
- <constraint>
Expected artifact:
- <one artifact>
Acceptance criteria:
- <criterion>
Gate to next stage:
- <what must be proven>
```

## Artifact gate

A lead MUST NOT delegate work until the work-item folder contains a verified `brief.md` and `status.md`.

- `brief.md` must have explicit scope, out-of-scope, acceptance criteria, required roles, and critical risks with owners.
- `status.md` must follow the format below and be updated after every stage transition, agent launch, or interruption, including any open obligations that still block closeout.
- If either artifact is missing, stale, or incomplete, the lead restores only the lead-owned task-memory state from persisted accepted artifacts BEFORE delegating any specialist role. Do not reconstruct missing specialist artifacts or factual findings from chat memory.
- The only exception is the additive fast lane where the lead records the decision in status.md instead.

### status.md format

```markdown
---
template: <template name>
orchestrator: main | lead
started: <YYYY-MM-DD>
updated: <YYYY-MM-DD HH:MM>
---

## Current state

- **Primary task**: <one active objective, e.g. "full-impact review of current change set">
- **Primary task status**: <active | side-interrupted | parked | closed>
- **Interruption marker**: <none | INTERRUPTED(no-artifact)>
- **Stage**: <current stage name or number>
- **Main conv role**: <what main conversation is doing: orchestrating | waiting for agents | reviewing artifact | idle>
- **Last accepted artifact**: <filename or "none">
- **Open obligations before closeout**: <none | remaining required work still inside admitted scope>

## Active agents

| Agent | Role | Status | Launched |
| --- | --- | --- | --- |
| <description> | <role> | running | <HH:MM> |

## Completed agents

| Agent | Role | Result | Artifact |
| --- | --- | --- | --- |
| <description> | <role> | PASS/REVISE/BLOCKED | <filename> |

## REVISE loop

| Field | Value |
| --- | --- |
| **Stage** | <stage name where REVISE occurred> |
| **Iteration** | <1-3, or "escalated"> |
| **Gate role** | <qa-engineer, security-reviewer, etc.> |
| **Last finding summary** | <one-line summary of what the gate found> |
| **Owner of next action** | <implementer role that must fix, or "user" if escalated> |

## Next action

<What happens next: which agent to launch, what artifact to review, or what decision to make.>
```

The REVISE loop section is optional — include it only when a stage has returned REVISE and the loop is active. Remove it when the loop resolves (PASS or escalation).

No-artifact interruption rule:
- A handoff interrupt or worker stall without an artifact does not count as a substantive REVISE artifact.
- Set `Primary task status: side-interrupted` and `Interruption marker: INTERRUPTED(no-artifact)` in `status.md` for orchestrator bookkeeping.
- Keep the stage open, and either rerun the same role with a tighter slice or route to the proper factual role.
- The lead must not synthesize the missing artifact or replace missing factual work inline.
- If the interrupted stage belongs to a full-impact review or verification pass, keep that review as the primary task until a review artifact is emitted or the user explicitly parks/cancels it.

## Response format

```text
1. Summary
2. Artifact
3. Risks / Unknowns
4. Recommended next role
5. Gate: PASS | REVISE | BLOCKED:<class> | RETURN(role)
```

- When a role makes a decision, it should clearly distinguish confirmed facts, assumptions, and judgment.
- If the main gap is missing evidence, recommend the appropriate factual role instead of escalating into opinion.
- `$consultant` replaces the Gate line with `5. Advisory status: NON-BLOCKING` and appends `6. Continuation prompt: <ready-to-send second prompt that begins with a direct imperative to continue and names the next concrete action>`.
- Consultant mode `external` stays external-only. If external execution is unavailable, batch closure stays open and the lead escalates to the user instead of downgrading to an internal-only run.
- `external-worker` and `external-reviewer` keep the standard gate line, but their artifact must also carry the external provenance header from `external-dispatch.md`.

### BLOCKED classification

When returning BLOCKED, specify the class:

| Class | Meaning | Orchestrator action |
| --- | --- | --- |
| `BLOCKED:dependency` | Cannot proceed — missing tool, environment, access, or information that no current agent can provide | Present to user for resolution |
| `BLOCKED:prerequisite` | Discovered adjacent work that must complete first (e.g., broken adjacent module, missing migration) | File in `work-items/bugs/` → user decides priority → resume when resolved |

If no class is specified, treat as `BLOCKED:dependency` (conservative default).

## Interaction rules

- The orchestrating owner controls routing: `$product-manager` for roadmap, `$lead` for delivery.
- Subagents produce accepted artifacts for the next role — they do not assign work to peers directly.
- If blocked by missing evidence, route back to the orchestrating owner for factual clarification.
- Reviewers report findings and gate outcomes; they do not manage implementation.
- When an upstream artifact is insufficient, return `REVISE` or `BLOCKED` instead of silently redefining the contract.

## Test ownership boundary

| Test type | Owner | When |
| --- | --- | --- |
| Unit tests for new/changed code | Implementer | Written as part of the implementation artifact |
| Regression tests for existing behavior | QA engineer | Written during verification if missing |
| Integration / end-to-end tests | QA engineer | Written or updated during verification |
| Contract-change test updates | Implementer | When QA classifies a failure as `contract-change` — the implementer who changed the behavior updates the tests |

If the plan specifies a different test ownership split, follow the plan. This table is the default when no plan-level override exists.

## Session logging

Every subagent MUST write a session log to `.reports/YYYY-MM/` before returning its final response when the session produced a result, made a routing decision, or completed a review. This rule applies equally to the main conversation and lead — see `AGENTS.md` § "Session logging rule" for the full contract and log format. Create the `YYYY-MM/` subdirectory if it does not exist. Session logs are summaries, not artifact copies.

## Structured completion report

For substantial tasks, prefer a structured closeout in the final summary:

- **Changed:** what was modified and why
- **Verified:** what was tested or checked, with evidence
- **Not verified:** what was not checked and why
- **Still open:** remaining required work to satisfy the current request, or `none`
- **Risks / follow-ups:** residual risks, deferred work, or known limitations

This is a recommended format for user-facing task completion, not a mandatory gate artifact. For pipeline handoffs, use the shared response format above.

## Gate questions

Ask these before advancing:

1. Is the artifact complete for its stage?
2. Is anything still assumed but unstated?
3. Did the stage stay within its role boundaries?
4. Are the allowed change surface and must-not-break surfaces explicit enough?
5. Is the next stage receiving only the context it truly needs?
6. Is an independent reviewer or human gate still required?
7. Is the blast radius still inside the approved change surface?
8. Is any admitted-scope obligation still open even though one sub-batch is finished?
