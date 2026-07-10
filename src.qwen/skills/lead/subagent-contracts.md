# Qwen Specialist Handoff Contract

Use this template whenever the main Qwen session delegates to a Qwen specialist role skill.

## Invocation rule

- Activate the matching role skill by name (dispatched as a subagent where the runtime supports skill-backed subagents, activated in-session otherwise), except for provider-backed external adapter routes.
- Do not role-play specialists inline when a matching role skill exists.
- Do not ask one role to own the whole feature.
- `$external-worker` and `$external-reviewer` are direct external launch routes, not internal skill-activation hosts. Do not satisfy them by spawning an internal helper or agent that then relays to another CLI.

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

Before closeout, run `scripts/validate-work-item-state.* --work-item <path>` or the installed equivalent when the repository exposes one. Before broad closeout, interruption recovery, or publication review, run `scripts/check-work-items-state.* --root <repo>` or the installed equivalent to scan all active work items. Example Qwen installs carry the universal hook/helper scripts under the installed extension's `scripts/` and `hooks/` directories; if the Qwen runtime cannot auto-trigger those hooks natively, use those installed helpers manually or through an approved wrapper rather than treating the backstop as absent. Closeout is blocked while the ledger contains running agents, duplicate run IDs, missing artifacts for `PASS`, `PASS` without evidence, stale running agents, or inconsistent `BLOCKED` / `REVISE` status.

## External dispatch contract

Use `external-dispatch.md` when the main Qwen session prefers or explicitly selects an external adapter.

- Resolve external routing in this order: `role eligibility -> provider selection -> CLI availability`.
- `$consultant` is advisory-only.
- `$external-worker` covers the full worker-side lane.
- `$external-reviewer` covers review and QA-side work only.
- There is no generic external adapter for owner roles such as `$product-manager` or `$lead`.
- If the selected external CLI is unavailable, the adapter is disabled and the main Qwen session reroutes explicitly.
- If the current runtime cannot launch the selected external provider directly, the route is unavailable; do not proxy it through an internal Qwen skill-activation host.
- `externalProvider: auto` resolves through the active named priority profile, not a line-specific default. Shipped production profiles are `balanced` and `quality-first`; shipped and repo-local production profiles stay on `codex | claude`. If a repository wants a Qwen demonstration lane, express that through a scalar explicit provider override, not a profile entry.
- Honor `externalCodexProfile` first when Codex is the resolved provider: `default` inherits `externalModelMode`; `gpt-5.6-sol-max` requests model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes; `gpt-5.6-luna` selects the fast/volume Codex model tier (a distinct model, `model_reasoning_effort = "medium"`, not an effort downgrade) and must record unavailable or deviated if that model cannot be verified against the installed runtime; `gpt-5.6-sol-xhigh` (shipped as default in the Codex/Claude packs) pins model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` regardless of `externalModelMode`. If Codex is resolved and the inherited model policy is pinned, start on model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` through a supported Codex config/profile path; only an explicitly configured repo-local fully autonomous low-reasoning worker lane may retry once on `gpt-5.6-luna` after usage-limit or quota exhaustion on the primary path, and the route must not silently downgrade below that floor. Example-only Qwen routes remain explicit/manual and do not add separate provider-local fallback keys to the shared schema.
- Honor `reserve` only when an advisory or review profile order reaches that symbolic supplemental candidate. It is separate from primary providers, appears after primary `claude`/`codex`, and must not be used for worker, implementation, code-generation, file-editing, or publication work.
- `parallelMode` is the general rule for whether independent helper lanes should be parallelized by judgment at all. External fan-out follows that rule instead of defining a separate global concurrency model.
- If the active lane policy asks for more than one external opinion, the main session may launch multiple independent external adapters in parallel and aggregate the returned artifacts fail closed.

## BLOCKED classes

| Class | Meaning |
|---|---|
| `BLOCKED:dependency` | Missing tool, environment, access, or information |
| `BLOCKED:prerequisite` | Adjacent issue must be resolved first |

## Mandatory rules

- The main Qwen session remains the orchestrator and owns stage progression.
- A specialist role returns one artifact for one gate.
- A specialist does not launch another specialist.
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
- `JSONL`: JSON Lines; one JSON object per line, used here for append-only execution events.
- `ledger`: append-only record of agent runs, gates, artifacts, and evidence for a work item.
- `PASS`: workflow state meaning the scoped artifact passed the relevant gate.
- `QA`: Quality Assurance; verification work for tests, regressions, and acceptance criteria.
- `Qwen`: Qwen provider line; here it is explicit example-only and `WEAK MODEL / NOT RECOMMENDED`.
- `status.md`: human-readable recovery summary for the active work item.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for example-only providers excluded from production `auto` routing.
