# Gemini Specialist Handoff Contract

Use this template whenever the main Gemini session delegates to a Gemini specialist subagent.

## Invocation rule

- Invoke the matching subagent tool by role name, or force it explicitly with `@role` at the beginning of the prompt, except for provider-backed external adapter routes.
- Do not role-play specialists inline when a matching Gemini subagent exists.
- Do not ask one subagent to own the whole feature.
- `$external-worker` and `$external-reviewer` are direct external launch routes, not Gemini subagent hosts. Do not satisfy them by spawning an internal helper/agent that then relays to another CLI.

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

## External dispatch contract

Use `external-dispatch.md` when the main Gemini session prefers or explicitly selects an external adapter.

- Resolve external routing in this order: `role eligibility -> provider selection -> CLI availability`.
- `$consultant` is advisory-only.
- `$external-worker` covers the full worker-side lane.
- `$external-reviewer` covers review and QA-side work only.
- There is no generic external adapter for owner roles such as `$product-manager` or `$lead`. If a request lands in one of those lanes, fail fast with an unsupported-route explanation instead of probing providers.
- If the selected external CLI is unavailable, the adapter is disabled and the main Gemini session reroutes explicitly.
- If the current runtime cannot launch the selected external provider directly, the route is unavailable; do not proxy it through a Gemini subagent host.
- `externalProvider: auto` resolves through the active named priority profile, not a line-specific default. `balanced` is the ordinary baseline; `gemini-crosscheck` is the profile that keeps Gemini in the non-visual advisory and review cross-check set. Explicit user override or documented repo-local heuristics may still prefer Gemini for image, icon, decorative visual, and other clearly visual lanes when that routing remains honest, but same-provider Gemini routing requires an explicit override.
- If Claude is the resolved provider, honor both `externalClaudeSecretMode` and `externalClaudeApiMode`.
- If the active lane policy asks for more than one external opinion, the main session may launch multiple independent external adapters in parallel and aggregate the returned artifacts fail closed.
- Independent external adapters may run in parallel when their scopes are disjoint and provider runtimes support concurrent non-interactive execution. If native internal slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.
- Same-provider reuse is allowed for independent external fan-out. Do not impose a one-instance-per-provider cap when multiple admitted artifacts or disjoint slices need the same helper/provider combination.
- `externalOpinionCounts` still governs distinct-provider opinion requirements for one lane; it does not limit brigade-style parallel launches across different independent lanes or slices.
- When the routing decision is "launch a bounded set of external helpers together", prefer the utility skill `external-brigade` so the brigade has one explicit plan, one ownership table, and one aggregated result surface.

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
