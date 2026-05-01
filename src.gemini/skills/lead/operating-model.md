# Gemini Lead Operating Model

This file is the Gemini-line orchestration reference for the common role principle.

## Structural truth

- Gemini `skills/` are the stable expertise layer.
- Gemini `agents/` are the preview specialist-team layer.
- Gemini subagents cannot call other subagents, so recursive orchestration does not live inside a Gemini subagent.
- The main Gemini session, with `$lead` active, is the orchestration owner for team-template execution.

## Routing model

| Template type | Owner | Specialist execution |
|---|---|---|
| `requiresLead: false` | main Gemini session | main session invokes the matching specialist subagents directly |
| `requiresLead: true` | main Gemini session under `$lead` | main session reads the team template, invokes the needed specialist subagents, and owns integration |

## Team-template source

Use:

- `../../agents/team-templates/quick-fix.json`
- `../../agents/team-templates/research.json`
- `../../agents/team-templates/review.json`
- `../../agents/team-templates/full-delivery.json`
- `../../agents/team-templates/security-sensitive.json`
- `../../agents/team-templates/performance-sensitive.json`
- `../../agents/team-templates/geometry-review.json`
- `../../agents/team-templates/combined-critical.json`

These templates are repo-local orchestration metadata, not a Gemini-native settings surface.

## Parallel execution

Parallel specialist runs are allowed only when:

- scopes are independent
- allowed change surfaces are disjoint
- one integration owner is explicit before QA or review

The main Gemini session launches the parallel specialist subagents. A Gemini subagent does not launch peers.

`parallelMode` is the general orchestrator rule for whether independent helper lanes should be parallelized by judgment at all. When the active external-routing profile asks for more than one external opinion, the main session may also launch multiple independent external adapters in parallel and aggregate them fail closed on top of that rule.

## Primary-task lock

- Keep exactly one primary in-progress task.
- Side requests may pause it, but do not replace it unless the user explicitly reprioritizes.
- After any side request, resume the primary task and state the next concrete step.
- Do not begin closeout work while a primary review or verification pass is still open.

## Execution continuity

- `PASS` advances immediately.
- `REVISE` stays in the same role for bounded correction.
- Escalate after 3 consecutive `REVISE` cycles on the same role and artifact.
- Do not stop at a partial batch when admitted-scope next work is already known.

## External adapters

Gemini-line external adapters use `.gemini/.agents-mode.yaml`.

Canonical provider semantics:

| Key | Meaning |
|---|---|
| `consultantMode` | consultant behavior toggle for Gemini-line routing; `disabled` skips consultant work by default, `internal` keeps consultant internal-only, and `external` allows consultant requests to use external routing |
| `externalClaudeApiMode` | controls the supplemental `claude-secret` candidate for `advisory.*` and `review.*` profile orders only; `disabled` removes it, `auto` allows it after primary `claude`/`codex`, and `force` keeps it available for advisory/review even when plain Claude is unavailable; never a primary-Claude retry, worker transport, or editing path; default `auto` |
| `parallelMode` | general helper parallelism rule across internal and external lanes; `manual` keeps ordinary fan-out explicit-only, `auto` leaves safe parallelism enabled by routing judgment, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified |
| `externalProvider: auto` | Resolve by the active named production priority profile and then apply the self-provider filter; shipped `balanced` keeps `auto` on `codex | claude` only |
| `externalProvider: codex` | explicit Codex CLI path |
| `externalProvider: claude` | explicit Claude CLI path |
| `externalProvider: gemini` | explicit self-provider override only; manual example or compatibility path, not a production recommendation |
| `externalProvider: qwen` | explicit native example or compatibility path only; not a production recommendation |
| `externalPriorityProfile` | selects the active named profile used for `auto` |
| `externalPriorityProfiles` | stores the profile -> lane -> ordered provider lists |
| `externalOpinionCounts` | stores how many distinct external opinions to collect per lane |
| `externalModelMode` | shared cross-provider model policy; `runtime-default` keeps provider runtime selection, `pinned-top-pro` pins the strongest documented production-provider model/profile path |

Gemini does not write `externalProvider: gemini` into the Gemini-line overlay because that would collapse into the current provider.
- Resolve any `external` request in this order: `role eligibility -> provider selection -> CLI availability`.
- Unsupported external requests fail fast. There is no generic external adapter for owner roles such as `$product-manager` or `$lead` on the Gemini line.
- An explicit request for `external` on an unsupported owner role changes the disclosure, not the eligibility. The main Gemini session must say the route is unsupported and reroute honestly.
- Gemini is `WEAK MODEL / NOT RECOMMENDED` on this line. Shipped and repo-local production `auto` profiles must keep Gemini and Qwen out of provider-order lists.
- Explicit Gemini or Qwen routing remains available only as a manual example or compatibility path.
- Independent external adapters may run in parallel when their scopes are disjoint, `parallelMode` permits ordinary parallel fan-out, provider runtimes support concurrent non-interactive execution, and the active profile or lane count asks for more than one opinion.
- Parallel external routing is not capped at one instance per helper or provider. If multiple admitted artifacts or disjoint slices honestly need the same provider, the main Gemini session may launch repeated same-provider external helpers concurrently.
- Treat same-lane multi-opinion collection and general external fan-out as different mechanisms: `externalOpinionCounts` governs distinct opinions for one lane, while brigade-style fan-out covers multiple independent lanes or slices on top of the general `parallelMode` rule.
- If native internal slot limits would otherwise block additional independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.
