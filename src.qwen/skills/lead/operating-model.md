# Qwen Lead Operating Model

This file is the Qwen-line orchestration reference for the common role principle.

## Structural truth

- Qwen `skills/` are the stable expertise layer.
- Qwen `agents/` are the explicit specialist-team layer.
- Orchestrarium keeps orchestration in the main Qwen session instead of collapsing routing and execution into one subagent.
- The main Qwen session, with `$lead` active, is the orchestration owner for team-template execution.

## Routing model

| Template type | Owner | Specialist execution |
|---|---|---|
| `requiresLead: false` | main Qwen session | main session invokes the matching specialist subagents directly |
| `requiresLead: true` | main Qwen session under `$lead` | main session reads the team template, invokes the needed specialist subagents, and owns integration |

## Team-template source

Use the JSON templates under `../../agents/team-templates/`. These templates are repo-local orchestration metadata, not a Qwen-native settings surface.

## Parallel execution

Parallel specialist runs are allowed only when:

- scopes are independent
- allowed change surfaces are disjoint
- one integration owner is explicit before QA or review

The main Qwen session launches the parallel specialist subagents. A Qwen subagent does not launch peers.

`parallelMode` is the general orchestrator rule for whether independent helper lanes should be parallelized by judgment at all. When the active external-routing profile asks for more than one external opinion, the main session may also launch multiple independent external adapters in parallel and aggregate them fail closed on top of that rule.

## External adapters

Qwen-line external adapters use `.qwen/.agents-mode.yaml`.

Canonical provider semantics:

| Key | Meaning |
|---|---|
| `consultantMode` | consultant behavior toggle for Qwen-line routing |
| `externalClaudeApiMode` | controls the supplemental `claude-secret` candidate for `advisory.*` and `review.*` profile orders only; never a primary-Claude retry, worker transport, or editing path |
| `parallelMode` | general helper parallelism rule across internal and external lanes |
| `externalProvider: auto` | resolve by the active named priority profile and then apply the self-provider filter; shipped production profiles stay on `codex | claude` only |
| `externalProvider: codex` | explicit Codex CLI path |
| `externalProvider: claude` | explicit Claude CLI path |
| `externalProvider: gemini` | explicit example-only compatibility path; `WEAK MODEL / NOT RECOMMENDED` |
| `externalProvider: qwen` | explicit example-only self-provider override; `WEAK MODEL / NOT RECOMMENDED` |
| `externalPriorityProfile` | selects the active named profile used for `auto` |
| `externalPriorityProfiles` | stores the `profile -> lane -> ordered provider list` map |
| `externalOpinionCounts` | stores how many distinct external opinions to collect per lane |
| `externalModelMode` | shared cross-provider model policy; `runtime-default` keeps provider runtime selection, `pinned-top-pro` pins the strongest documented production-provider path |

Rules:

- Resolve any `external` request in this order: `role eligibility -> provider selection -> CLI availability`.
- Unsupported external requests fail fast. There is no generic external adapter for owner roles such as `$product-manager` or `$lead` on the Qwen line.
- The shipped shared profiles do not hardwire Qwen into visual lanes. If a clearly visual worker, review, or advisory lane should demonstrate Qwen, do that through a scalar explicit provider override, not through `externalPriorityProfiles`.
- Parallel external routing is not capped at one instance per helper or provider. If multiple admitted artifacts or disjoint slices honestly need the same provider, the main Qwen session may launch repeated same-provider external helpers concurrently.
- `externalOpinionCounts` governs distinct opinions for one lane; brigade-style fan-out covers multiple independent lanes or slices on top of the general `parallelMode` rule.
