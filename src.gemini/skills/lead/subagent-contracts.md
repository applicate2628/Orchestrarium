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

## agent-runs.jsonl format

When task memory is configured, every delegated role, external adapter, consultant sweep, and main-session gate action that produces or accepts an artifact must append one JSON object to `agent-runs.jsonl` in the same work-item directory.

The ledger is machine-readable execution state; `status.md` remains the human-readable recovery summary. A `PASS` in `status.md` is not accepted unless the corresponding ledger event has `gate: "PASS"`, `status: "completed"`, an artifact path, and at least one evidence entry.

Minimum required fields are defined by `shared/schemas/agent-runs.schema.json`: `schemaVersion`, `runId`, `workItem`, `role`, `executionRole`, `status`, `gate`, `scope`, `startedAt`, and `updatedAt`.

When `scripts/agent-run-ledger.*` or an installed equivalent is available, prefer its `append` command so the event is validated and rolled back on failure. Use its `init` command for one-time migration of legacy work items with missing status sections or ledger files. Manual JSONL append is acceptable only when no helper is available.

Before closeout, run `scripts/validate-work-item-state.* --work-item <path>` or the installed equivalent when the repository exposes one. Before broad closeout, interruption recovery, or publication review, run `scripts/check-work-items-state.* --root <repo>` or the installed equivalent to scan all active work items. Closeout is blocked while the ledger contains running agents, duplicate run IDs, missing artifacts for `PASS`, `PASS` without evidence, stale running agents, or inconsistent `BLOCKED` / `REVISE` status.

## External dispatch contract

Use `external-dispatch.md` when the main Gemini session prefers or explicitly selects an external adapter.

- Resolve external routing in this order: `role eligibility -> provider selection -> CLI availability`.
- `$consultant` is advisory-only.
- `$external-worker` covers the full worker-side lane.
- `$external-reviewer` covers review and QA-side work only.
- There is no generic external adapter for owner roles such as `$product-manager` or `$lead`. If a request lands in one of those lanes, fail fast with an unsupported-route explanation instead of probing providers.
- If the selected external CLI is unavailable, the adapter is disabled and the main Gemini session reroutes explicitly.
- If the current runtime cannot launch the selected external provider directly, the route is unavailable; do not proxy it through a Gemini subagent host.
- `externalProvider: auto` resolves through the active named priority profile, not a line-specific default. Shipped production profiles are `balanced` and `quality-first`, and both stay on `codex | claude`. Gemini and Qwen are example-only providers and must stay out of shipped or repo-local production `auto` profiles.
- Honor `externalModelMode` first after provider resolution. If Codex is the resolved provider and the model policy is pinned, start on `gpt-5.5 --reasoning-effort xhigh`; only an explicitly configured repo-local fully autonomous low-reasoning worker lane may retry once on `gpt-5.3-codex-spark` after usage-limit or quota exhaustion on the primary path, and the route must not silently downgrade below that floor. Explicit Gemini example routes remain manual example or compatibility runs rather than a pinned production model policy.
- Honor `reserve` only when an advisory or review profile order reaches that symbolic supplemental candidate. It is separate from primary providers, appears after primary `claude`/`codex`, and must not be used for worker, implementation, code-generation, file-editing, or publication work.
- `parallelMode` is the general rule for whether independent helper lanes should be parallelized by judgment at all. External fan-out follows that rule instead of defining a separate global concurrency model.
- If the active lane policy asks for more than one external opinion, the main session may launch multiple independent external adapters in parallel and aggregate the returned artifacts fail closed.
- Independent external adapters may run in parallel when their scopes are disjoint, `parallelMode` permits ordinary parallel fan-out, and provider runtimes support concurrent non-interactive execution. If native internal slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.
- Same-provider reuse is allowed for independent external fan-out. Do not impose a one-instance-per-provider cap when multiple admitted artifacts or disjoint slices need the same helper/provider combination.
- `externalOpinionCounts` still governs distinct-provider opinion requirements for one lane; it does not replace the general `parallelMode` rule or limit brigade-style parallel launches across different independent lanes or slices.
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

## Terms and Abbreviations

- `agent-run-ledger.*`: helper script family that initializes legacy work-item ledger files and appends validated `agent-runs.jsonl` events.
- `agent-runs.jsonl`: JSONL execution ledger stored beside `status.md` for machine-readable work-item state.
- `check-work-items-state.*`: helper script family that checks every active work item under a repository root.
- `BLOCKED`: workflow state for a real missing dependency, prerequisite, or unavailable route.
- `reserve`: symbolic supplemental read-only candidate for advisory/review lanes only; it is separate from primary providers and not valid for worker or mutating routes.
- `CLI`: Command-Line Interface; a provider or tool invoked from a shell.
- `evidence`: concrete verification data such as a command, artifact path, review result, log summary, or observed output supporting a gate.
- `Gemini`: Google Gemini provider line; here it is explicit example-only and `WEAK MODEL / NOT RECOMMENDED`.
- `JSONL`: JSON Lines; one JSON object per line, used here for append-only execution events.
- `ledger`: append-only record of agent runs, gates, artifacts, and evidence for a work item.
- `PASS`: workflow state meaning the scoped artifact passed the relevant gate.
- `QA`: Quality Assurance; verification work for tests, regressions, and acceptance criteria.
- `status.md`: human-readable recovery summary for the active work item.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for example-only providers excluded from production `auto` routing.
