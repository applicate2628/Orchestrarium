# Qwen Specialist Handoff Contract

Use this template whenever the main Qwen session delegates to a Qwen specialist subagent.

## Invocation rule

- Invoke the matching subagent tool by role name, or force it explicitly with `@role` at the beginning of the prompt, except for provider-backed external adapter routes.
- Do not role-play specialists inline when a matching Qwen subagent exists.
- Do not ask one subagent to own the whole feature.
- `$external-worker` and `$external-reviewer` are direct external launch routes, not Qwen subagent hosts. Do not satisfy them by spawning an internal helper or agent that then relays to another CLI.

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

Use `external-dispatch.md` when the main Qwen session prefers or explicitly selects an external adapter.

- Resolve external routing in this order: `role eligibility -> provider selection -> CLI availability`.
- `$consultant` is advisory-only.
- `$external-worker` covers the full worker-side lane.
- `$external-reviewer` covers review and QA-side work only.
- There is no generic external adapter for owner roles such as `$product-manager` or `$lead`.
- If the selected external CLI is unavailable, the adapter is disabled and the main Qwen session reroutes explicitly.
- If the current runtime cannot launch the selected external provider directly, the route is unavailable; do not proxy it through a Qwen subagent host.
- `externalProvider: auto` resolves through the active named priority profile, not a line-specific default. Shipped and repo-local production profiles stay on `codex | claude`. If a repository wants a Qwen demonstration lane, express that through a scalar explicit provider override, not a profile entry.
- Honor `externalModelMode` first after provider resolution. If Codex is the resolved provider and the model policy is pinned, start on `gpt-5.4 --reasoning-effort xhigh`; only `worker.long-autonomous` or another explicitly fully autonomous low-reasoning worker lane may retry once on `gpt-5.3-codex-spark` after usage-limit or quota exhaustion on the primary path, and the route must not silently downgrade below that floor. Example-only Qwen routes remain explicit/manual and do not add separate provider-local fallback keys to the shared schema.
- Honor `externalClaudeApiMode` only when an advisory or review profile order reaches the supplemental `claude-secret` candidate. It is separate from primary `claude`, appears after primary `claude`/`codex`, and must not be used for worker, implementation, code-generation, file-editing, or publication work.
- `parallelMode` is the general rule for whether independent helper lanes should be parallelized by judgment at all. External fan-out follows that rule instead of defining a separate global concurrency model.
- If the active lane policy asks for more than one external opinion, the main session may launch multiple independent external adapters in parallel and aggregate the returned artifacts fail closed.

## BLOCKED classes

| Class | Meaning |
|---|---|
| `BLOCKED:dependency` | Missing tool, environment, access, or information |
| `BLOCKED:prerequisite` | Adjacent issue must be resolved first |

## Mandatory rules

- The main Qwen session remains the orchestrator and owns stage progression.
- A specialist subagent returns one artifact for one gate.
- A subagent does not launch another subagent.
- If evidence is missing, route to the correct factual role instead of guessing.
- If a review artifact is still missing, the review is not complete.
