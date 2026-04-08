# Subagent Contracts

Handoff templates and response format for lead-to-specialist delegation.

## Execution mechanism

Every specialist invocation MUST use the **Agent tool** with the matching `subagent_type` parameter. The handoff template below becomes the agent's `prompt`. The orchestrator (main conversation or lead) MUST NOT role-play specialists inline — each role runs in an isolated agent context.

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
- `status.md` must follow the format below and be updated after every stage transition, agent launch, or interruption.
- If either artifact is missing, stale, or incomplete, the lead restores them BEFORE delegating any specialist role.
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

- **Stage**: <current stage name or number>
- **Main conv role**: <what main conversation is doing: orchestrating | waiting for agents | reviewing artifact | idle>
- **Last accepted artifact**: <filename or "none">

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
- `$consultant` replaces the Gate line with `5. Advisory status: NON-BLOCKING`.

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

## Structured completion report

For substantial tasks, prefer a structured closeout in the final summary:

- **Changed:** what was modified and why
- **Verified:** what was tested or checked, with evidence
- **Not verified:** what was not checked and why
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
