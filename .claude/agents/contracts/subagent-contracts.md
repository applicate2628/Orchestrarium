# Subagent Contracts

Handoff templates and response format for lead-to-specialist delegation.

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
- `status.md` must have a current snapshot with stage, last accepted artifact, and next concrete action.
- If either artifact is missing, stale, or incomplete, the lead restores them BEFORE delegating any specialist role.
- The only exception is the additive fast lane where the lead records the decision in status.md instead.

## Response format

```text
1. Summary
2. Artifact
3. Risks / Unknowns
4. Recommended next role
5. Gate: PASS | REVISE | BLOCKED | RETURN(role)
```

- When a role makes a decision, it should clearly distinguish confirmed facts, assumptions, and judgment.
- If the main gap is missing evidence, recommend the appropriate factual role instead of escalating into opinion.
- `$consultant` replaces the Gate line with `5. Advisory status: NON-BLOCKING`.

## Interaction rules

- The orchestrating owner controls routing: `$product-manager` for roadmap, `$lead` for delivery.
- Subagents produce accepted artifacts for the next role — they do not assign work to peers directly.
- If blocked by missing evidence, route back to the orchestrating owner for factual clarification.
- Reviewers report findings and gate outcomes; they do not manage implementation.
- When an upstream artifact is insufficient, return `REVISE` or `BLOCKED` instead of silently redefining the contract.

## Gate questions

Ask these before advancing:

1. Is the artifact complete for its stage?
2. Is anything still assumed but unstated?
3. Did the stage stay within its role boundaries?
4. Are the allowed change surface and must-not-break surfaces explicit enough?
5. Is the next stage receiving only the context it truly needs?
6. Is an independent reviewer or human gate still required?
7. Is the blast radius still inside the approved change surface?
