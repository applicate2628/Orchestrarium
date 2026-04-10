# Gemini Specialist Handoff Contract

Use this template whenever the main Gemini session delegates to a Gemini specialist subagent.

## Invocation rule

- Invoke the matching subagent tool by role name, or force it explicitly with `@role` at the beginning of the prompt.
- Do not role-play specialists inline when a matching Gemini subagent exists.
- Do not ask one subagent to own the whole feature.

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

## Response format

```text
1. Summary
2. Artifact
3. Risks / Unknowns
4. Recommended next role
5. Gate: PASS | REVISE | BLOCKED:<class> | RETURN(role)
```

## BLOCKED classes

| Class | Meaning |
|---|---|
| `BLOCKED:dependency` | Missing tool, environment, access, or information |
| `BLOCKED:prerequisite` | Adjacent issue must be resolved first |

## Mandatory rules

- The main Gemini session remains the orchestrator and owns stage progression.
- A specialist subagent returns one artifact for one gate.
- A subagent does not launch another subagent.
- If evidence is missing, route to the correct factual role instead of guessing.
- If a review artifact is still missing, the review is not complete.
